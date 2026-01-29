import json
import os
import platform
import subprocess
import traceback
from typing import Any, Dict, List, Optional
import docker
import structlog
from pathlib import Path
from uuid import UUID

from autostack_engine.utils.database.models.components.models import Component, ComponentType, Connection, Framework
from autostack_engine.utils.database.models.project.models import Project
from autostack_engine.utils.database.models.technologies.models import Technology, TechnologyCategory
from autostack_engine.utils.database.mongo_client import DatabaseManager
from autostack_engine.utils.orchestration.models import BaseService

logger = structlog.get_logger()


class ComposeYamlGenerator:
    """Generates docker-compose.yml from components, technologies, and connections"""
    
    # Default images and configurations for common technologies
    TECH_DEFAULTS = {
        'postgresql': {
            'image': 'postgres:{version}',
            'default_version': '16',
            'default_port': 5432,
            'default_env': {
                'POSTGRES_PASSWORD': 'postgres',
                'POSTGRES_USER': 'postgres',
                'POSTGRES_DB': 'app_db'
            },
            'volume_mount': '/var/lib/postgresql/data'
        },
        'mysql': {
            'image': 'mysql:{version}',
            'default_version': '8',
            'default_port': 3306,
            'default_env': {
                'MYSQL_ROOT_PASSWORD': 'root',
                'MYSQL_DATABASE': 'app_db'
            },
            'volume_mount': '/var/lib/mysql'
        },
        'mongodb': {
            'image': 'mongo:{version}',
            'default_version': 'latest',
            'default_port': 27017,
            'default_env': {},
            'volume_mount': '/data/db'
        },
        'redis': {
            'image': 'redis:{version}',
            'default_version': 'alpine',
            'default_port': 6379,
            'default_env': {},
            'volume_mount': '/data'
        },
        'rabbitmq': {
            'image': 'rabbitmq:{version}-management',
            'default_version': '3',
            'default_port': 5672,
            'additional_ports': [15672],  # Management UI
            'default_env': {
                'RABBITMQ_DEFAULT_USER': 'guest',
                'RABBITMQ_DEFAULT_PASS': 'guest'
            },
            'volume_mount': '/var/lib/rabbitmq'
        },
        'kafka': {
            'image': 'confluentinc/cp-kafka:{version}',
            'default_version': 'latest',
            'default_port': 9092,
            'default_env': {
                'KAFKA_ZOOKEEPER_CONNECT': 'zookeeper:2181',
                'KAFKA_ADVERTISED_LISTENERS': 'PLAINTEXT://kafka:9092',
                'KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR': '1'
            },
            'depends_on': ['zookeeper']
        },
        'zookeeper': {
            'image': 'confluentinc/cp-zookeeper:{version}',
            'default_version': 'latest',
            'default_port': 2181,
            'default_env': {
                'ZOOKEEPER_CLIENT_PORT': '2181',
                'ZOOKEEPER_TICK_TIME': '2000'
            },
            'volume_mount': '/var/lib/zookeeper'
        },
        'elasticsearch': {
            'image': 'elasticsearch:{version}',
            'default_version': '8.11.0',
            'default_port': 9200,
            'additional_ports': [9300],
            'default_env': {
                'discovery.type': 'single-node',
                'xpack.security.enabled': 'false'
            },
            'volume_mount': '/usr/share/elasticsearch/data'
        },
        'nginx': {
            'image': 'nginx:{version}',
            'default_version': 'alpine',
            'default_port': 80,
            'default_env': {},
            'volume_mount': '/etc/nginx'
        }
    }
    
    @staticmethod
    def generate(project_name: str, components: List[Dict[str, Any]], 
                 technologies: List[Dict[str, Any]] = None) -> str:
        """Generate docker-compose.yml content with components and technologies"""
        lines = ["services:"]
        
        all_volumes = set()
        
        # Add technology services (infrastructure)
        if technologies:
            for tech in technologies:
                service_name = tech['service_name']
                lines.append(f"  {service_name}:")
                lines.append(f"    image: {tech['image']}")
                lines.append(f"    container_name: {project_name}_{service_name}")
                lines.append(f"    restart: unless-stopped")
                
                if tech.get('ports'):
                    lines.append(f"    ports:")
                    for port in tech['ports']:
                        lines.append(f"      - \"{port}:{port}\"")
                
                if tech.get('environment'):
                    lines.append(f"    environment:")
                    for key, value in tech['environment'].items():
                        lines.append(f"      {key}: {value}")
                
                if tech.get('volumes'):
                    lines.append(f"    volumes:")
                    for volume in tech['volumes']:
                        lines.append(f"      - {volume}")
                        # Extract volume name if it's a named volume
                        if ':' in volume and not volume.startswith('.') and not volume.startswith('/'):
                            vol_name = volume.split(':')[0]
                            all_volumes.add(vol_name)
                
                if tech.get('depends_on'):
                    lines.append(f"    depends_on:")
                    for dep in tech['depends_on']:
                        lines.append(f"      - {dep}")
                
                if tech.get('networks'):
                    lines.append(f"    networks:")
                    for network in tech['networks']:
                        lines.append(f"      - {network}")
                
                lines.append("")
        
        # Add component services (application services)
        for comp in components:
            service_name = comp['service_name']
            lines.append(f"  {service_name}:")
            lines.append(f"    build:")
            lines.append(f"      context: ./{comp['directory']}")
            lines.append(f"    container_name: {project_name}_{service_name}")
            lines.append(f"    restart: unless-stopped")
            
            if comp.get('ports'):
                lines.append(f"    ports:")
                for port in comp['ports']:
                    host_port = port.get('host', port.get('container'))
                    container_port = port.get('container', port.get('host'))
                    lines.append(f"      - \"{host_port}:{container_port}\"")
            
            if comp.get('environment'):
                lines.append(f"    environment:")
                for key, value in comp['environment'].items():
                    lines.append(f"      {key}: {value}")
            
            if comp.get('depends_on'):
                lines.append(f"    depends_on:")
                for dep in comp['depends_on']:
                    lines.append(f"      - {dep}")
            
            if comp.get('volumes'):
                lines.append(f"    volumes:")
                for volume in comp['volumes']:
                    lines.append(f"      - {volume}")
            
            if comp.get('networks'):
                lines.append(f"    networks:")
                for network in comp['networks']:
                    lines.append(f"      - {network}")
            
            lines.append("")
        
        # Add volumes section if there are any named volumes
        if all_volumes:
            lines.append("volumes:")
            for volume in sorted(all_volumes):
                lines.append(f"  {volume}:")
                lines.append(f"    driver: local")
            lines.append("")
        
        # Add default network
        lines.append("networks:")
        lines.append(f"  {project_name}_network:")
        lines.append(f"    driver: bridge")
        
        return "\n".join(lines)
    
    @staticmethod
    def build_technology_config(tech: Technology, project_name: str) -> Dict[str, Any]:
        """Build service configuration from technology data"""
        tech_name = tech.name.lower()
        service_name = f"{tech_name}"
        
        # Get defaults for this technology
        defaults = ComposeYamlGenerator.TECH_DEFAULTS.get(tech_name, {})
        
        # Determine image
        version = tech.version if tech.version else defaults.get('default_version', 'latest')
        image_template = defaults.get('image', f'{tech_name}:{version}')
        image = image_template.format(version=version)
        
        # Determine ports
        ports = []
        if tech.port:
            ports.append(tech.port)
        elif defaults.get('default_port'):
            ports.append(defaults['default_port'])
        
        # Add additional ports if defined
        if defaults.get('additional_ports'):
            ports.extend(defaults['additional_ports'])
        
        # Build environment variables
        environment = {}
        if defaults.get('default_env'):
            environment.update(defaults['default_env'])
        if tech.environment_variables:
            environment.update(tech.environment_variables)
        
        # Build volumes
        volumes = []
        volume_mount = defaults.get('volume_mount')
        if volume_mount:
            volume_name = f"{project_name}_{service_name}_data"
            volumes.append(f"{volume_name}:{volume_mount}")
        
        # Custom volumes from configuration
        if tech.configuration and tech.configuration.get('volumes'):
            volumes.extend(tech.configuration['volumes'])
        
        config = {
            'service_name': service_name,
            'image': image,
            'ports': ports,
            'environment': environment,
            'volumes': volumes,
            'depends_on': defaults.get('depends_on', []),
            'networks': [f"{project_name}_network"]
        }
        
        return config



class ProductionService(BaseService):
    """Service for managing production environment configuration"""
    
    service_name = "PRODUCTION"
    
    async def generate_docker_compose(self, project_id: str) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Generate docker-compose.yml for production environment.
        
        Args:
            project_id: The project ID
            
        Returns:
            tuple: (success: bool, compose_path: Optional[str], error_message: Optional[str])
        """
        try:
            success = await self.create_production_environment(project_id)
            
            if success:
                # Get project to return compose path
                project = await Project.get(project_id)
                if project:
                    compose_path = str(Path(project.metadata.directory) / 'docker-compose.yml')
                    self.log_info(f"Generated docker-compose.yml at {compose_path}")
                    return True, compose_path, None
                else:
                    return False, None, "Project not found after compose generation"
            else:
                return False, None, "Failed to generate docker-compose.yml"
                
        except Exception as e:
            error_msg = f"Error generating docker-compose: {traceback.format_exc()}"
            self.log_error(error_msg)
            return False, None, str(e)
        
    async def fetch_project_data(self, project_id: str) -> Dict[str, Any]:
        """Fetch project, components, technologies, and connections from MongoDB"""
        try:
            db = DatabaseManager()
            await db.connect([Project, Component, Connection, Technology])
            
            project = await Project.get(project_id)
            if not project:
                logger.error(f"Project '{project_id}' not found")
                return None
            
            try:
                project_uuid = UUID(project_id) if isinstance(project_id, str) else project_id
            except ValueError:
                logger.error(f"Invalid UUID format: {project_id}")
                return None
            
            self.log_info(f"Fetching data for project_id: {project_uuid}")
        
            components = await Component.find({'project_id': project_uuid}).to_list(None)
            connections = await Connection.find({'project_id': project_uuid}).to_list(None)
            technologies = await Technology.find({
                'project_id': project_uuid,
                'enabled': True
            }).to_list(None)
            
            self.log_info(f"Found {len(components)} components")
            self.log_info(f"Found {len(connections)} connections")
            self.log_info(f"Found {len(technologies)} technologies")
            
            return {
                'project': project,
                'components': components,
                'connections': connections,
                'technologies': technologies
            }
        except Exception as e:
            self.log_error("Error fetching project data", error=str(e), exc_info=True)
            return None
    
    
    async def create_production_environment(self, project_id: str) -> bool:
        """Main method to create production environment"""
        try:
            # Fetch data from database
            data = await self.fetch_project_data(project_id)
            if not data:
                return False
            
            project = data['project']
            components = data['components']
            connections = data['connections']
            technologies = data['technologies']
            
            self.log_info(f"Found {len(components)} components to configure")
            self.log_info(f"Found {len(technologies)} technologies to configure")
            
            project_path = Path(project.metadata.directory)
            project_path.mkdir(parents=True, exist_ok=True)
            project_name = project_path.name
            
            INFRASTRUCTURE_COMPONENT_TYPES = {
                ComponentType.DATABASE,
                ComponentType.CACHE,
                ComponentType.EXTERNAL
            }
            
            INFRASTRUCTURE_TECHNOLOGIES = {
                "postgresql", "mysql", "mongodb", "sqlite",  
                "redis", "memcached",                       
                "rabbitmq", "kafka",                         
            }
            
            missing_dockerfiles = []
            for component in components:
                is_infrastructure_component = component.type in INFRASTRUCTURE_COMPONENT_TYPES
                is_infrastructure_tech = (
                    component.technology and 
                    component.technology.lower() in INFRASTRUCTURE_TECHNOLOGIES
                )
                
                if is_infrastructure_component or is_infrastructure_tech:
                    self.log_info(f"Skipping Dockerfile check for infrastructure component: {component.name} ({component.type})")
                    continue
                    
                comp_dir_name = component.directory if hasattr(component, 'directory') else '.'
                comp_dir = project_path / comp_dir_name
                dockerfile_path = comp_dir / 'Dockerfile'
                
                if not dockerfile_path.exists():
                    missing_dockerfiles.append(component.name)
                    self.log_warning(f"Dockerfile not found for {component.name} at {dockerfile_path}")
            
            if missing_dockerfiles:
                self.log_error(f"Missing Dockerfiles for application components: {', '.join(missing_dockerfiles)}")
                self.log_error("Please ensure application components are scaffolded first via components.create topic")
                return False
            
            # Build technology service configs (infrastructure)
            tech_services = []
            tech_service_names = []
            for tech in technologies:
                # Skip runtime technologies
                if tech.category == TechnologyCategory.RUNTIME:
                    self.log_info(f"Skipping runtime technology: {tech.name}")
                    continue
                    
                tech_config = ComposeYamlGenerator.build_technology_config(tech, project_name)
                tech_services.append(tech_config)
                tech_service_names.append(tech_config['service_name'])
                self.log_info(f"Added technology service: {tech_config['service_name']} ({tech.category})")
            
            connection_map = {}
            for conn in connections:
                # Beanie models use attributes, but check for dict-like access just in case
                source_id = str(conn.source) if hasattr(conn, 'source') else str(conn.get('source'))
                if source_id not in connection_map:
                    connection_map[source_id] = []
                connection_map[source_id].append(conn)
            
            # Collect component service configs
            component_services = []
            for component in components:
                service_config = self.build_service_config(
                    component, connection_map, tech_service_names, project_name
                )
                component_services.append(service_config)
                self.log_info(f"Added component service: {service_config['service_name']}")
            
            total_services = len(tech_services) + len(component_services)
            self.log_info(f"Total services to add: {total_services} "
                        f"({len(tech_services)} infrastructure, {len(component_services)} components)")
            
            if total_services == 0:
                self.log_error("No services to configure!")
                return False
            
            # Generate docker-compose.yml in project root
            compose_content = ComposeYamlGenerator.generate(
                project_name, component_services, tech_services
            )
            compose_path = project_path / 'docker-compose.yml'
            self.log_info(f"Generated compose content")
            
            with open(compose_path, 'w') as f:
                f.write(compose_content)
            
            self.log_info(f"Generated docker-compose.yml at {compose_path}")
            self.log_info(f"Infrastructure services: {[s['service_name'] for s in tech_services]}")
            self.log_info(f"Component services: {[s['service_name'] for s in component_services]}")
            
            return True
            
        except Exception as e:
            self.log_error("Error creating production environment",
                        project_id=project_id, error=str(e), exc_info=True)
            return False
        
    def build_service_config(self, component: Component, connection_map: Dict, 
                           tech_services: List[str], project_name: str) -> Dict:
        """Build service configuration from component data"""
        service_name = component.name.lower().replace(' ', '_')
        
        # Get the directory path and clean it
        comp_directory = component.directory if hasattr(component, 'directory') else '.'
        
        config = {
            'service_name': service_name,
            'directory': comp_directory,
            'framework': component.framework if hasattr(component, 'framework') else Framework.NONE,
            'ports': component.ports if hasattr(component, 'ports') else [],
            'environment': component.environment_variables if hasattr(component, 'environment_variables') else {},
            'volumes': component.volumes if hasattr(component, 'volumes') else [],
            'depends_on': [],
            'networks': [f"{project_name}_network"]
        }
        
        # Add dependencies from connections (other components)
        component_id = str(component.id)
        for conn in connection_map.get(component_id, []):
            target_id = str(conn.target_id) if hasattr(conn, 'target_id') else conn.get('target_id')
            if target_id != component_id:
                target_name = conn.target_name if hasattr(conn, 'target_name') else conn.get('target_name', '')
                target_name = target_name.lower().replace(' ', '_')
                if target_name and target_name not in config['depends_on']:
                    config['depends_on'].append(target_name)
        
        # Add dependencies on technology services (databases, caches, etc.)
        for tech_service in tech_services:
            if tech_service not in config['depends_on']:
                config['depends_on'].append(tech_service)
        
        return config

           
            
