import json
import os
import subprocess
import threading
import traceback
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from autostack_engine.utils.database.models.project.models import Project
from autostack_engine.utils.database.models.technologies.models import Technology, TechnologyCategory
from autostack_engine.utils.database.mongo_client import DatabaseManager
from autostack_engine.utils.orchestration.models import BaseService
from autostack_engine.utils.schema.models.technologies import TechnologyManager


class TechnologyService(BaseService):
    """Service for managing project technologies and development environment"""
    
    service_name = "TECHNOLOGY"
    
    async def create_technologies(
        self, 
        project_id: str, 
        technologies: list[Dict[str, Any]],
        initialize_devbox: bool = True
    ) -> tuple[bool, Optional[list[str]], Optional[str]]:
        """
        Create technologies for a project.
        
        Args:
            project_id: The project ID
            technologies: List of technology configurations
            initialize_devbox: Whether to initialize devbox environment
            
        Returns:
            tuple: (success: bool, tech_ids: Optional[list], error_message: Optional[str])
        """
        try:
            db = DatabaseManager()
            await db.connect([Project, Technology])
            
            # Verify project exists
            project = await Project.get(project_id)
            if not project:
                return False, None, f"Project '{project_id}' does not exist"
            
            # Transform and create technologies
            tech_configs = []
            for tech_data in technologies:
                env_vars_input = tech_data.get('environment_variables')
                if isinstance(env_vars_input, list):
                    # List of dicts or EnvironmentVariables objects
                    env_vars = {}
                    for env in env_vars_input:
                        # Handle both dict-like and object-like (with .name / .value attributes)
                        if hasattr(env, 'name') and hasattr(env, 'value'):
                            env_vars[env.name] = env.value
                        elif isinstance(env, dict):
                            env_vars[env['name']] = env['value']
                        else:
                            self.log_warning(f"Invalid env var item in {tech_data.get('name')}")
                    tech_data['environment_variables'] = env_vars if env_vars else None

                elif hasattr(env_vars_input, 'name') and hasattr(env_vars_input, 'value'):
                    # Single EnvironmentVariables object
                    tech_data['environment_variables'] = {env_vars_input.name: env_vars_input.value}

                elif env_vars_input in ([], None):
                    tech_data['environment_variables'] = None

                else:
                    # Unexpected type – log and skip or set to None
                    self.log_warning(f"Unexpected environment_variables type for {tech_data.get('name')}: {type(env_vars_input)}")
                    tech_data['environment_variables'] = None
                
                # Handle configuration
                if tech_data.get('configuration') == []:
                    tech_data['configuration'] = None
                elif isinstance(tech_data.get('configuration'), str):
                    try:
                        tech_data['configuration'] = json.loads(tech_data['configuration'])
                    except json.JSONDecodeError:
                        self.log_warning(f"Invalid JSON in configuration for {tech_data.get('name')}")
                        tech_data['configuration'] = None
                
                # Ensure required fields
                if 'id' not in tech_data:
                    tech_data['id'] = str(uuid4())
                tech_data['project_id'] = project_id
                
                tech_config = Technology(**tech_data)
                tech_configs.append(tech_config)
            
            # Insert technologies
            await Technology.insert_many(tech_configs)
            tech_ids = [str(tech.id) for tech in tech_configs]
            
            self.log_info(f"Created {len(tech_configs)} technologies for project '{project_id}'")
            
            # Initialize devbox environment
            if initialize_devbox:
                await self._initialize_devbox_environment(project.metadata.directory, tech_configs)
            
            return True, tech_ids, None
            
        except Exception as e:
            error_msg = f"Error creating technologies: {traceback.format_exc()}"
            self.log_error(error_msg)
            return False, None, str(e)
    
    async def _initialize_devbox_environment(self, project_directory: str, technologies: list[Technology]):
        """Initialize devbox environment with technologies"""
        try:
            project_directory = os.path.abspath(project_directory)
            
            # Check if devbox is available
            try:
                subprocess.run(["devbox", "version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.log_warning("devbox command not found. Skipping devbox initialization.")
                return False

            # Initialize devbox if needed
            devbox_json_path = os.path.join(project_directory, "devbox.json")
            if not os.path.exists(devbox_json_path):
                self.log_info("Initializing devbox in project directory")
                init_result = subprocess.run(
                    ["devbox", "init"],
                    cwd=project_directory,
                    capture_output=True,
                    text=True
                )
                if init_result.returncode != 0:
                    self.log_error(f'Error initializing devbox: {init_result.stderr}')
                    return False
            
            # Get package specifications
            package_specs = TechnologyManager.get_devbox_technologies(technologies)
            
            if not package_specs:
                self.log_info("No devbox packages to install")
                return True
            
            def run_devbox_async():
                result = subprocess.run(
                    ["devbox", "add"] + package_specs,
                    cwd=project_directory,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.log_info("Devbox packages installed successfully")
                else:
                    self.log_error(f'Error adding packages: {result.stderr}')
            
            # Run in background thread
            threading.Thread(target=run_devbox_async, daemon=True).start()
            
            return True
            
        except Exception as e:
            self.log_error(f"Error initializing devbox: {e}", exc_info=True)
            return False
    
    async def update_technology(self, tech_id: str, updates: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Update a technology configuration"""
        try:
            db = DatabaseManager()
            await db.connect([Technology])
            
            tech = await Technology.get(tech_id)
            if not tech:
                return False, f"Technology '{tech_id}' not found"
            
            # Update allowed fields
            if "name" in updates:
                tech.name = updates["name"]
            if "version" in updates:
                tech.version = updates["version"]
            if "enabled" in updates:
                tech.enabled = updates["enabled"]
            if "port" in updates:
                tech.port = updates["port"]
            if "environment_variables" in updates:
                tech.environment_variables = updates["environment_variables"]
            if "configuration" in updates:
                tech.configuration = updates["configuration"]
            
            await tech.save()
            
            self.log_info(f"Updated technology '{tech_id}'")
            return True, None
            
        except Exception as e:
            error_msg = f"Error updating technology: {str(e)}"
            self.log_error(error_msg)
            return False, error_msg
    
    async def delete_technology(self, tech_id: str) -> tuple[bool, Optional[str]]:
        """Delete a technology"""
        try:
            db = DatabaseManager()
            await db.connect([Technology])
            
            tech = await Technology.get(tech_id)
            if not tech:
                return False, f"Technology '{tech_id}' not found"
            
            tech_name = tech.name
            await tech.delete()
            
            self.log_info(f"Deleted technology '{tech_name}' (ID: {tech_id})")
            return True, None
            
        except Exception as e:
            error_msg = f"Error deleting technology: {str(e)}"
            self.log_error(error_msg)
            return False, error_msg
    
    async def list_technologies(self, project_id: str) -> list[Technology]:
        """List all technologies for a project"""
        try:
            db = DatabaseManager()
            await db.connect([Technology])
            
            project_uuid = UUID(project_id) if isinstance(project_id, str) else project_id
            return await Technology.find({'project_id': project_uuid}).to_list(None)
        except Exception as e:
            self.log_error(f"Error listing technologies: {e}")
            return []