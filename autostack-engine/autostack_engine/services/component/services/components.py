import json
import subprocess
import asyncio
import traceback
from uuid import UUID
from pathlib import Path
from typing import List, Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from autostack_engine.utils.database.models.activities.models import ActivityLog, ActivityType
from autostack_engine.utils.database.models.project.models import Project
from autostack_engine.utils.database.mongo_client import DatabaseManager
from autostack_engine.utils.orchestration.models import BaseService
from autostack_engine.utils.database.models.components.models import (
    Component, 
    Connection, 
    ComponentManager,
    ComponentType,
    ComponentStatus,
    Framework
)


class DockerfileGenerator:
    """Generates Dockerfiles using Jinja2 templates"""
    
    def __init__(self):
        """Initialize Jinja2 environment"""
        template_dir = Path(__file__).parent / 'templates' / 'dockerfiles'
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['Dockerfile']),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def get_dockerfile(self, framework: str, context: Dict[str, Any] = None) -> str:
        """Get Dockerfile content for framework using Jinja2 template"""
        if context is None:
            context = {}
        
        try:
            fw = Framework(framework.lower())
            template_name = f"{fw.value}.dockerfile.j2"
        except ValueError:
            template_name = "default.dockerfile.j2"
        
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Error rendering Dockerfile template: {e}")
            # Fallback to default template
            template = self.env.get_template("default.dockerfile.j2")
            return template.render(**context)
    
    def get_nginx_config(self, framework: str) -> str:
        """Get nginx configuration based on framework"""
        # Use SPA config for frameworks that need client-side routing
        spa_frameworks = ['react', 'angular', 'vue', 'svelte']
        
        if framework.lower() in spa_frameworks:
            return """
            server {
                listen 80;
                server_name localhost;
                
                root /usr/share/nginx/html;
                index index.html;
                
                # Security headers
                add_header X-Frame-Options "SAMEORIGIN" always;
                add_header X-Content-Type-Options "nosniff" always;
                add_header X-XSS-Protection "1; mode=block" always;
                
                # Gzip compression
                gzip on;
                gzip_vary on;
                gzip_min_length 1024;
                gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json application/javascript;
                
                # SPA routing - all requests go to index.html
                location / {
                    try_files $uri $uri/ /index.html;
                }
                
                # Cache static assets
                location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
                    expires 1y;
                    add_header Cache-Control "public, immutable";
                }
                
                # Don't cache index.html
                location = /index.html {
                    add_header Cache-Control "no-cache, no-store, must-revalidate";
                    expires 0;
                }
            }"""
        else:
            return """
            server {
                listen 80;
                server_name localhost;
                
                root /usr/share/nginx/html;
                index index.html index.htm;
                
                # Security headers
                add_header X-Frame-Options "SAMEORIGIN" always;
                add_header X-Content-Type-Options "nosniff" always;
                add_header X-XSS-Protection "1; mode=block" always;
                
                # Gzip compression
                gzip on;
                gzip_vary on;
                gzip_min_length 1024;
                gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json application/javascript;
                
                location / {
                    try_files $uri $uri/ =404;
                }
                
                # Cache static assets
                location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
                    expires 1y;
                    add_header Cache-Control "public, immutable";
                }
            }"""


class ComponentService(BaseService):
    """Service for managing components and connections"""
    
    service_name = "COMPONENT"
    
    def __init__(self):
        super().__init__()
        self.dockerfile_generator = DockerfileGenerator()
    
    async def create_components(
        self,
        project_id: str,
        components_data: list[Dict[str, Any]],
        connections_data: Optional[list[Dict[str, Any]]] = None,
        initialize_locally: bool = True
    ) -> tuple[bool, Optional[list[str]], Optional[str]]:
        """
        Create components and connections for a project.
        
        Args:
            project_id: The project ID
            components_data: List of component configurations
            connections_data: List of connection configurations
            initialize_locally: Whether to scaffold components locally
            
        Returns:
            tuple: (success: bool, component_ids: Optional[list], error_message: Optional[str])
        """
        try:
            db = DatabaseManager()
            await db.connect([Project, Component, Connection])
            
            # Verify project exists
            project = await Project.get(project_id)
            if not project:
                return False, None, f"Project '{project_id}' does not exist"
            
            # Create components
            created_components = []
            for comp_data in components_data:
                # Handle ID field
                if 'id' in comp_data:
                    comp_data['component_id'] = comp_data['id']
                    del comp_data['id']
                
                # Parse framework enum
                if comp_data.get('framework') and isinstance(comp_data['framework'], str):
                    try:
                        comp_data['framework'] = Framework(comp_data['framework'].lower())
                    except ValueError:
                        self.log_warning(f"Invalid framework '{comp_data['framework']}', setting to None")
                        comp_data['framework'] = None
                
                # Parse component type
                if isinstance(comp_data.get('type'), str):
                    comp_data['type'] = ComponentType(comp_data['type'].lower())
                
                # Set directory
                if not comp_data.get('directory'):
                    type_value = comp_data['type'].value
                    comp_data['directory'] = f"{type_value}/{comp_data['component_id']}"
                
                component = Component(**comp_data)
                created_components.append(component)
            
            await Component.insert_many(created_components)
            component_ids = [comp.component_id for comp in created_components]
            
            self.log_info(f"Created {len(created_components)} components for project '{project_id}'")
            
            # Create connections
            if connections_data:
                connections = []
                for conn_data in connections_data:
                    connection = Connection(**conn_data)
                    connections.append(connection)
                
                await Connection.insert_many(connections)
                self.log_info(f"Created {len(connections)} connections")
            
            # Initialize components locally
            if initialize_locally:
                await self._initialize_components_locally(
                    project.metadata.directory,
                    created_components
                )
            
            return True, component_ids, None
            
        except Exception as e:
            error_msg = f"Error creating components: {traceback.format_exc()}"
            self.log_error(error_msg)
            return False, None, str(e)
    
    async def _initialize_components_locally(self, project_directory: str, components: list[Component]):
        """Initialize components locally (simplified - delegates to existing logic)"""
        try:
            project_path = Path(project_directory).resolve()
            
            # Group components by whether they need scaffolding
            scaffold_components = [c for c in components if c.requires_scaffolding()]
            service_components = [c for c in components if c.type in [ComponentType.DATABASE, ComponentType.CACHE]]
            
            self.log_info(f"Found {len(scaffold_components)} components requiring scaffolding")
            self.log_info(f"Found {len(service_components)} service components")
            
            # Install required packages for all components
            all_packages = set()
            for component in components:
                packages = component.get_required_devbox_packages()
                all_packages.update(packages)
            
            if all_packages:
                await self._add_devbox_packages(project_path, list(all_packages))
            
            # Scaffold components that need it - run sequentially to avoid conflicts
            for component in scaffold_components:
                await self._scaffold_component(project_path, component)
            
            # Generate devbox service configurations for databases/caches
            if service_components:
                await self._generate_service_configs(project_path, service_components)
            
            # Generate Dockerfiles for all components
            for component in components:
                await self._generate_component_dockerfile(project_path, component)
            
            self.log_info("All components initialized locally")
            return True
            
        except Exception as e:
            self.log_error(f"Error initializing components locally: {e}")
            return False
        
    async def _generate_component_dockerfile(self, project_path: Path, component: Component):
        """Generate Dockerfile for a component"""
        try:
            component_dir = project_path / component.directory
            component_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare context for template rendering
            context = {
                'component_id': component.component_id,
                'component_name': component.name,
                'technology': component.technology,
                'port': component.port if hasattr(component, 'port') else None,
                'environment_variables': component.environment_variables if hasattr(component, 'environment_variables') else {}
            }
            
            # Generate Dockerfile content
            framework = component.framework if hasattr(component, 'framework') else Framework.NONE
            dockerfile_content = self.dockerfile_generator.get_dockerfile(framework.value if framework else 'none', context)
            
            # Write Dockerfile
            dockerfile_path = component_dir / 'Dockerfile'
            with open(dockerfile_path, 'w') as f:
                f.write(dockerfile_content)
            
            self.log_info(f"Created Dockerfile for {component.component_id} at {dockerfile_path}")
            
            # Generate nginx.conf for frontend frameworks
            frontend_frameworks = ['react', 'nextjs', 'angular', 'vue', 'svelte', 'vanilla']
            if framework and framework.value in frontend_frameworks:
                nginx_conf = self.dockerfile_generator.get_nginx_config(framework.value)
                nginx_path = component_dir / 'nginx.conf'
                
                with open(nginx_path, 'w') as f:
                    f.write(nginx_conf)
                
                self.log_info(f"Created nginx.conf for {component.component_id}")
            
            return True
            
        except Exception as e:
            self.log_error(f"Error generating Dockerfile for {component.component_id}: {e}",)
            return False
    
    async def _add_devbox_packages(self, project_path: Path, packages: List[str]):
        """Add packages to devbox using devbox shell"""
        try:
            # Check if devbox is available
            try:
                subprocess.run(["devbox", "version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.log_warning("devbox command not found. Skipping package addition.")
                return False

            self.log_info(f"Adding devbox packages: {packages}")
            
            # Run devbox add synchronously within async context
            # Start the devbox shell process
            process = await asyncio.to_thread(
                subprocess.Popen,
                ["devbox", "shell"],
                cwd=str(project_path),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Send the add command to the shell and then exit
            commands = "devbox add " + " ".join(packages) + "\nexit\n"
            stdout, stderr = await asyncio.to_thread(process.communicate, commands)

            if process.returncode == 0:
                self.log_info("Devbox packages added successfully")
                return True
            else:
                self.log_error(f"Error adding devbox packages: {stderr}")
                return False
                
        except Exception as e:
            self.log_error(f"Error adding devbox packages: {e}")
            return False
    
    async def _scaffold_component(self, project_path: Path, component: Component):
        """Scaffold a component using its framework CLI with devbox run"""
        try:
            await ComponentManager.update_component_status(
                component.component_id,
                ComponentStatus.SCAFFOLDING
            )
            component_dir = project_path / component.directory
            component_dir.mkdir(parents=True, exist_ok=True)

            if component.technology == "nodejs":
                self.log_info(f"Clearing npm cache for {component.component_id} to prevent JSON parse issues")
                clear_cmd = ["devbox", "run", "npm", "cache", "clean", "--force"]
                clear_result = await asyncio.to_thread(
                    subprocess.run,
                    clear_cmd,
                    cwd=str(project_path.resolve()),  
                    capture_output=True,
                    text=True,
                    timeout=9000
                )
                if clear_result.returncode != 0:
                    self.log_warning(f"npm cache clean failed (may be harmless, continuing): {clear_result.stderr}")
                else:
                    self.log_info("npm cache cleared successfully")
                
            scaffold_cmd = self._get_scaffold_command(component)
            if not scaffold_cmd:
                self.log_warning(f"No scaffold command for {component.framework}")
                await ComponentManager.update_component_status(
                    component.component_id,
                    ComponentStatus.RUNNING
                )
                return

            self.log_info(f"Scaffolding {component.component_id} with {scaffold_cmd}")

            if component.framework == Framework.ANGULAR:
                parent_dir = component_dir.parent
                parent_dir.mkdir(parents=True, exist_ok=True)
                temp_name = f"temp_{component.component_id}"
                temp_dir = parent_dir / temp_name

                full_cmd = [
                    "devbox", "run", "npx", "@angular/cli", "new", temp_name,
                    "--routing=true", "--style=css", "--skip-git=true", "--skip-install"
                ]

                self.log_info(f"Running Angular scaffolding in {parent_dir} -> creating {temp_dir}")

                result = await asyncio.to_thread(
                    subprocess.run,
                    full_cmd,
                    cwd=str(parent_dir.resolve()),
                    capture_output=True,
                    text=True,
                    timeout=9000 
                )

                if result.returncode != 0:
                    self.log_error(f"Angular scaffolding failed: {result.stderr}")
                    await ComponentManager.update_component_status(component.component_id, ComponentStatus.FAILED)
                    return False

                temp_project_dir_path = project_path
                temp_project_dir_path.mkdir(parents=True, exist_ok=True)
                temp_dir_path = temp_project_dir_path / temp_name
                
                if not temp_dir_path.exists():
                    self.log_error(f"Temporary Angular project directory not found at {temp_dir}")
                    self.log_error(f"Current contents of parent {parent_dir}: {list(parent_dir.glob('*'))}")
                    await ComponentManager.update_component_status(component.component_id, ComponentStatus.FAILED)
                    return False

                self.log_info(f"Moving files from {temp_dir} to {component_dir}")

                component_dir.mkdir(parents=True, exist_ok=True)
                for item in temp_dir_path.iterdir():
                    target = component_dir / item.name
                    if target.exists():
                        if target.is_dir():
                            import shutil
                            shutil.rmtree(target)
                        else:
                            target.unlink()
                    item.rename(target)

                
                if temp_dir_path.exists():
                    temp_dir_path.rmdir()
                self.log_info("Angular files moved successfully")

            elif component.framework == Framework.DJANGO:
                cwd = str(component_dir)
                full_cmd = ["devbox", "run"] + scaffold_cmd 
            else:
                # General case
                cwd = str(component_dir)
                full_cmd = ["devbox", "run"] + scaffold_cmd

            if component.framework != Framework.ANGULAR:  
                result = await asyncio.to_thread(
                    subprocess.run,
                    full_cmd,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=9000 
                )
                if result.returncode != 0:
                    self.log_error(f"Scaffolding failed for {component.component_id}: {result.stderr}")
                    await ComponentManager.update_component_status(component.component_id, ComponentStatus.FAILED)
                    return False

            # Post-scaffolding steps (common)
            if component.environment_variables:
                await self._create_env_file(component_dir, component.environment_variables)

            await self._initialize_project_dependencies(component_dir, component)

            await ComponentManager.update_component_status(
                component.component_id,
                ComponentStatus.RUNNING
            )
            self.log_info(f"Successfully scaffolded {component.component_id}")
            return True

        except Exception as e:
            self.log_error(f"Scaffolding error: {traceback.format_exc()}")
            await ComponentManager.update_component_status(
                component.component_id,
                ComponentStatus.FAILED
            )
            return False
    
    
    async def update_component(self, component_id: str, updates: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Update a component"""
        try:
            db = DatabaseManager()
            await db.connect([Component])
            
            component = await Component.find_one({"component_id": component_id})
            if not component:
                return False, f"Component '{component_id}' not found"
            
            # Update allowed fields
            if "name" in updates:
                component.name = updates["name"]
            if "port" in updates:
                component.port = updates["port"]
            if "environment_variables" in updates:
                component.environment_variables = updates["environment_variables"]
            if "volumes" in updates:
                component.volumes = updates["volumes"]
            
            await component.save()
            
            self.log_info(f"Updated component '{component_id}'")
            return True, None
            
        except Exception as e:
            error_msg = f"Error updating component: {str(e)}"
            self.log_error(error_msg)
            return False, error_msg
    
    def _get_scaffold_command(self, component: Component) -> List[str]:
        """Get the scaffold command based on framework"""
        framework_commands = {
            Framework.DJANGO: ["django-admin", "startproject", component.component_id, "."],
            Framework.FLASK: ["pip", "install", "flask"],
            Framework.FASTAPI: ["pip", "install", "fastapi", "uvicorn"],
            Framework.EXPRESS: ["npx", "express-generator", ".", "--no-view"],
            Framework.NESTJS: ["npx", "@nestjs/cli", "new", component.component_id, "--skip-git"],
            Framework.REACT: ["npm", "create", "vite@latest", ".", "--", "--template", "react"],
            Framework.NEXTJS: ["npx", "create-next-app@latest", ".", "--yes", "--no-eslint"],
            Framework.ANGULAR: ["npx", "@angular/cli", "new", component.component_id, "--routing=true", "--style=css", "--skip-git=true", "--skip-install"], 
            Framework.VUE: ["npm", "create", "vite@latest", ".", "--", "--template", "vue"],  # Switched to Vite
            Framework.SVELTE: ["npm", "create", "vite@latest", ".", "--", "--template", "svelte"],  # Switched to Vite
            Framework.VANILLA: ["npm", "init", "-y"] if component.technology == "nodejs" else ["python", "-m", "venv", "venv"],
            Framework.NONE: ["npm", "init", "-y"] if component.technology == "nodejs" else ["python", "-m", "venv", "venv"],
        }
        
        if component.framework in framework_commands:
            return framework_commands[component.framework]
        
        # Default commands based on technology
        if component.technology == "python":
            return ["python", "-m", "venv", "venv"]
        elif component.technology == "nodejs":
            return ["npm", "init", "-y"]
        
        return []
    
    async def _initialize_project_dependencies(self, component_dir: Path, component: Component):
        """Initialize project dependencies based on technology"""
        try:
            if component.technology == "python":
                await self._setup_python_project(component_dir, component)
            elif component.technology == "nodejs":
                await self._setup_nodejs_project(component_dir, component)
        except Exception as e:
            self.log_error(f"Error initializing project dependencies: {e}")
    
    async def _setup_python_project(self, component_dir: Path, component: Component):
        """Setup Python project with virtual environment and dependencies"""
        try:
            # Create requirements.txt if it doesn't exist
            requirements_file = component_dir / "requirements.txt"
            if not requirements_file.exists():
                with open(requirements_file, 'w') as f:
                    # Add framework-specific dependencies
                    if component.framework == Framework.DJANGO:
                        f.write("Django>=4.0,<5.0\ndaphne\n")
                    elif component.framework == Framework.FLASK:
                        f.write("Flask>=2.0\n")
                    elif component.framework == Framework.FASTAPI:
                        f.write("fastapi>=0.68.0\nuvicorn>=0.15.0\n")
                
                self.log_info(f"Created requirements.txt for {component.component_id}")
            
            # Install dependencies using devbox shell
            # Start the devbox shell process for pip install
            process = await asyncio.to_thread(
                subprocess.Popen,
                ["devbox", "shell"],
                cwd=str(component_dir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Send the pip install command to the shell and then exit
            pip_command = "pip install -r requirements.txt\nexit\n"
            stdout, stderr = await asyncio.to_thread(process.communicate, pip_command)

            result = subprocess.CompletedProcess(
                args=["devbox", "shell"],
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr
            )
            
            if result.returncode == 0:
                self.log_info(f"Installed Python dependencies for {component.component_id}")
            else:
                self.log_error(f"Error installing Python dependencies: {result.stderr}")
                
        except Exception as e:
            self.log_error(f"Error setting up Python project: {e}")
    
    async def _setup_nodejs_project(self, component_dir: Path, component: Component):
        """Setup Node.js project with dependencies"""
        try:
            package_json = component_dir / "package.json"
            if not package_json.exists():
                self.log_warning(f"No package.json found for {component.component_id}")
                return
            
            # Install dependencies using devbox shell
            full_command = [
                "devbox", "run", "--",
                "bash", "-c",
                f"cd {component_dir} && npm install"
            ]
            result = await asyncio.to_thread(
                subprocess.run,
                full_command,
                cwd=str(component_dir),
                capture_output=True,
                text=True,
                timeout=9000
            )
            
            if result.returncode == 0:
                self.log_info(f"Installed Node.js dependencies for {component.component_id}")
            else:
                self.log_error(f"Error installing Node.js dependencies: {result.stderr}")
                
        except Exception as e:
            self.log_error(f"Error setting up Node.js project: {e}")
    
    async def _create_env_file(self, component_dir: Path, env_vars: Dict[str, Any]):
        """Create .env file for component"""
        try:
            env_file = component_dir / '.env'
            with open(env_file, 'w') as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            
            self.log_info(f"Created .env file at {env_file}")
        except Exception as e:
            self.log_error(f"Error creating .env file: {e}")
    
    async def _generate_service_configs(self, project_path: Path, service_components: List[Component]):
        """Generate devbox service configurations for databases and caches"""
        try:
            services_config = {}
            
            for component in service_components:
                service_name = component.component_id.replace('-', '_')
                
                # Basic service configuration
                service_config = {
                    "command": self._get_service_command(component),
                }
                
                if component.environment_variables:
                    service_config["env"] = component.environment_variables
                
                if component.port:
                    service_config["port"] = component.port
                
                services_config[service_name] = service_config
            
            # Update devbox.json with services
            devbox_json_path = project_path / "devbox.json"
            if devbox_json_path.exists():
                with open(devbox_json_path, 'r') as f:
                    devbox_config = json.load(f)
                
                if "shell" not in devbox_config:
                    devbox_config["shell"] = {}
                
                if "services" not in devbox_config["shell"]:
                    devbox_config["shell"]["services"] = {}
                
                devbox_config["shell"]["services"].update(services_config)
                
                with open(devbox_json_path, 'w') as f:
                    json.dump(devbox_config, f, indent=2)
                
                self.log_info(f"Added {len(services_config)} services to devbox.json")
            
        except Exception as e:
            self.log_error(f"Error generating service configs: {e}")
    
    def _get_service_command(self, component: Component) -> str:
        """Get the service start command based on technology"""
        command_map = {
            "postgresql": "postgres -D $PGDATA",
            "postgres": "postgres -D $PGDATA",
            "redis": "redis-server",
            "mongodb": "mongod --dbpath=$MONGODB_DATA",
            "mysql": "mysqld",
        }
        
        return command_map.get(component.technology.lower(), component.technology)
    
    async def delete_component(self, component_id: str, delete_files: bool = False) -> tuple[bool, Optional[str]]:
        """Delete a component"""
        try:
            db = DatabaseManager()
            await db.connect([Component, Project, ActivityLog])
            
            component = await Component.get(component_id)
            if not component:
                return False, f"Component '{component_id}' not found"
            
            component_name = component.name
            
            # Delete files if requested
            if delete_files and hasattr(component, 'directory'):
                try:
                    project = await Project.get(component.project_id)
                    if project:
                        component_path = Path(project.metadata.directory) / component.directory
                        if component_path.exists():
                            import shutil
                            shutil.rmtree(component_path)
                            self.log_info(f"Deleted component directory: {component_path}")
                except Exception as e:
                    self.log_warning(f"Could not delete component directory: {e}")
            
            await component.delete()
            activity = ActivityLog(
                activity_type=ActivityType.DELETE_COMPONENT,
                project_id=component.project_id,
                project_name=project.name
            )
            
            await activity.insert()
            
            self.log_info(f"Deleted component '{component_name}' (ID: {component_id})")
            return True, None
            
        except Exception as e:
            error_msg = f"Error deleting component: {str(e)}"
            self.log_error(error_msg)
            return False, error_msg
    
    async def list_components(self, project_id: str) -> list[Component]:
        """List all components for a project"""
        try:
            db = DatabaseManager()
            await db.connect([Component])
            
            project_uuid = UUID(project_id) if isinstance(project_id, str) else project_id
            return await Component.find({'project_id': project_uuid}).to_list(None)
        except Exception as e:
            self.log_error(f"Error listing components: {e}")
            return []

