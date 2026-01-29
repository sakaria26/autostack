import { inject, Injectable } from '@angular/core';
import { Apollo, gql } from 'apollo-angular';
import { map, Observable } from 'rxjs';

export interface ProjectMetadata {
  created_date?: string | null;
  lastModified?: string | null;
  tags?: string[] | null;
  environment?: string | null;
  directory?: string | null;
}

export interface GitInfo {
  latestCommit?: string | null;
  branch?: string | null;
  is_dirty?: boolean | null;
  commits?: string[] | null;
}

export interface ProjectResult {
  id: string;
  name: string;
  author?: string | null;
  description?: string | null;
  version: string;
  status?: string | null;
  metadata?: ProjectMetadata | null;
  gitInfo?: GitInfo | null;
  avatarDataUrl: string;
  avatarHash: string;
}

interface EnvironmentVariable {
  name: string;
  value: string;
}

interface Configuration {
  name: string;
  value: string;
}

interface Technology {
  name: string;
  version: string;
  category?: string;
  port?: number;
  enabled: boolean;
  environment_variables?: EnvironmentVariable[];
  configuration?: Configuration[];
}

interface Component {
  component_id: string;
  type: string;
  name: string;
  technology?: string;
  framework?: string;
  port?: number;
  environment_variables?: Record<string, any>;
  dependencies?: string[];
}

interface Connection {
  source: string;
  target: string;
  type: string;
  port?: number;
}

export interface ProjectArchitecture {
  project_id: string;
  project_name: string;
  technologies: Technology[];
  components: Component[];
  connections: Connection[];
  metadata: {
    component_count: number;
    connection_count: number;
    technology_count: number;
  };
}

interface ArchitectureResponse {
  success: boolean;
  data?: ProjectArchitecture;
  error?: string;
  message?: string;
}

export interface ProjectCreatedResponse {
  success: boolean;
  projectId: string;
  error: string;
  message: string;
}

enum TechnologyCategory {
  RUNTIME = 'RUNTIME',
  DATABASE = 'DATABASE',
  CACHE = 'CACHE',
  QUEUE = 'QUEUE',
  SERVICE = 'SERVICE',
}

enum ComponentTypeInput {
  DATABASE = 'DATABASE',
  CACHE = 'CACHE',
  API = 'API',
  WEB = 'WEB',
  GATEWAY = 'GATEWAY',
  EXTERNAL = 'EXTERNAL',
}

interface DeleteResponse {
  success: boolean;
  message?: string;
  error?: string;
}

export interface GitInitialiseResponse {
  success: boolean;
  git_info: GitInfo;
  message?: string;
  error?: string;
}

interface ComponentInfo {
  componentId: string;
  name: string;
  framework?: string;
  technology: string;
  dependencies: string[];
}

export interface ComponentsResponse {
  project_id: string;
  components: ComponentInfo[];
  success: boolean;
  error?: string;
  message: string;
}

export interface ProductionEnvironment {
  project_id: string;
  project_name: string;
  compose_file: string;
  compose_file_exists: boolean;
  containers: Array<{
    name: string;
    status: string;
    image: string;
    ports: any[];
    id: string;
  }>;
  container_count: number;
  project_directory: string;
  generated: boolean;
}

export interface ProductionEnvironmentResponse {
  success: boolean;
  data?: ProductionEnvironment;
  error?: string;
  message?: string;
}

@Injectable({
  providedIn: 'root',
})
export class ProjectService {
  private apollo = inject(Apollo);

  /**
   * Fetch all projects (basic info)
   */
  fetchAllProjects(): Observable<ProjectResult[]> {
    const FETCH_ALL_PROJECTS = gql`
      query FetchAllProjects {
        fetchAllProjects {
          id
          name
          author
          description
          version
          status
          metadata {
            createdDate
            lastModified
            tags
            environment
            directory
          }
          gitInfo {
            latestCommit
            branch
            isDirty
            commits
          }
          avatarDataUrl
          avatarHash
        }
      }
    `;

    return this.apollo
      .query<{ fetchAllProjects: ProjectResult[] }>({
        query: FETCH_ALL_PROJECTS,
        fetchPolicy: 'network-only',
      })
      .pipe(
        map((result) => {
          const data = result.data?.fetchAllProjects;
          // Ensure we always return an array
          if (!data) return [];
          return Array.isArray(data) ? data : [data];
        })
      );
  }

  /**
   * Fetch single project by ID (basic info)
   */
  fetchProjectById(projectId: string): Observable<ProjectResult> {
    const FETCH_PROJECT_ID = gql`
      query FetchProject($projectId: String!) {
        fetchProject(projectId: $projectId) {
          id
          name
          author
          description
          version
          status
          metadata {
            createdDate
            lastModified
            tags
            environment
            directory
          }
          gitInfo {
            latestCommit
            branch
            isDirty
            commits
          }
          avatarDataUrl
          avatarHash
        }
      }
    `;

    return this.apollo
      .query<{ fetchProject: ProjectResult }>({
        query: FETCH_PROJECT_ID,
        variables: { projectId },
        fetchPolicy: 'network-only',
      })
      .pipe(map((result) => result.data?.fetchProject!));
  }

  /**
   * Fetch full project architecture (components, connections, technologies)
   */
  fetchProjectArchitecture(projectId: string): Observable<ProjectArchitecture> {
    const FETCH_PROJECT_ARCHITECTURE = gql`
      query FetchProjectArchitecture($projectId: String!) {
        fetchProjectArchitecture(projectId: $projectId) {
          success
          data
          error
          message
        }
      }
    `;

    return this.apollo
      .query<{ fetchProjectArchitecture: ArchitectureResponse }>({
        query: FETCH_PROJECT_ARCHITECTURE,
        variables: { projectId },
        fetchPolicy: 'network-only',
      })
      .pipe(
        map((result) => {
          const response = result.data?.fetchProjectArchitecture;
          if (response?.success && response.data) {
            return response.data;
          }
          throw new Error(response?.error || 'Failed to fetch architecture');
        })
      );
  }

  /**
   * Create a full project from schema
   */
  createFullProject(
    schema: any,
    chatId: string
  ): Observable<ProjectCreatedResponse> {
    const input = this.transformToFullProjectInput(schema, chatId);
    console.log(input);
    const CREATE_FULL_PROJECT_DETAILED = gql`
      mutation CreateFullProject($input: FullProjectInput!) {
        createFullProject(input: $input) {
          success
          projectId
          error
          message
        }
      }
    `;

    return this.apollo
      .mutate<{ createFullProject: ProjectCreatedResponse }>({
        mutation: CREATE_FULL_PROJECT_DETAILED,
        variables: { input },
      })
      .pipe(map((result) => result.data!.createFullProject));
  }

  /**
   * Delete a project
   */
  deleteProject(
    projectId: string,
    deleteFiles: boolean = true
  ): Observable<DeleteResponse> {
    const DELETE_PROJECT = gql`
      mutation DeleteProject($projectId: String!, $deleteFiles: Boolean) {
        deleteProject(projectId: $projectId, deleteFiles: $deleteFiles) {
          success
          message
          error
        }
      }
    `;

    return this.apollo
      .mutate<{ deleteProject: DeleteResponse }>({
        mutation: DELETE_PROJECT,
        variables: {
          projectId: projectId,
          deleteFiles: deleteFiles,
        },
      })
      .pipe(map((result) => result.data!.deleteProject));
  }

  initialiseGit(projectId: string): Observable<GitInitialiseResponse> {
    const INITIALISE_GIT = gql`
      mutation InitialiseGit($projectId: String!) {
        initialiseGit(projectId: $projectId) {
          success
          gitInfo {
            latestCommit
            branch
            isDirty
            commits
          }
          message
          error
        }
      }
    `;

    return this.apollo
      .mutate<{ initialiseGit: GitInitialiseResponse }>({
        mutation: INITIALISE_GIT,
        variables: {
          projectId: projectId,
        },
      })
      .pipe(map((result) => result.data!.initialiseGit));
  }

  updateProject(
    projectId: string,
    updates: {
      name?: string;
      author?: string;
      description?: string;
      version?: string;
      tags?: string[];
    }
  ): Observable<ProjectCreatedResponse> {
    const UPDATE_PROJECT = gql`
      mutation UpdateProject(
        $projectId: String!
        $name: String
        $author: String
        $description: String
        $version: String
        $tags: [String!]
      ) {
        updateProject(
          projectId: $projectId
          name: $name
          author: $author
          description: $description
          version: $version
          tags: $tags
        ) {
          success
          projectId
          error
          message
        }
      }
    `;

    return this.apollo
      .mutate<{ updateProject: ProjectCreatedResponse }>({
        mutation: UPDATE_PROJECT,
        variables: {
          projectId,
          name: updates.name,
          author: updates.author,
          description: updates.description,
          version: updates.version,
          tags: updates.tags,
        },
      })
      .pipe(map((result) => result.data!.updateProject));
  }

  fetchProjectComponents(projectId: string): Observable<ComponentsResponse> {
    const FETCH_PROJECT_COMPONENTS = gql`
      query FetchProjectComponents($projectId: String!) {
        fetchProjectComponents(projectId: $projectId) {
          project_id
          success
          error
          message
          components {
            componentId
            name
            framework
            technology
            dependencies
          }
        }
      }
    `;

    return this.apollo
      .query<{ fetchProjectComponents: ComponentsResponse }>({
        query: FETCH_PROJECT_COMPONENTS,
        variables: { projectId },
        fetchPolicy: 'network-only',
      })
      .pipe(map((result) => result.data?.fetchProjectComponents!));
  }

  deleteComponent(componentId: string): Observable<DeleteResponse> {
    const DELETE_COMPONENT = gql`
      mutation DeleteComponent($componentId: String!, $deleteFiles: Boolean) {
        deleteComponent(componentId: $componentId, deleteFiles: $deleteFiles) {
          success
          message
          error
        }
      }
    `;

    return this.apollo
      .mutate<{ deleteComponent: DeleteResponse }>({
        mutation: DELETE_COMPONENT,
        variables: {
          componentId: componentId,
          deleteFiles: true,
        },
      })
      .pipe(map((result) => result.data!.deleteComponent));
  }

  fetchProductionEnvironment(
    projectId: string
  ): Observable<ProductionEnvironmentResponse> {
    const FETCH_PRODUCTION_ENVIRONMENT = gql`
      query FetchProductionEnvironment($projectId: String!) {
        fetchProductionEnvironment(projectId: $projectId) {
          success
          data
          error
          message
        }
      }
    `;

    return this.apollo
      .query<{ fetchProductionEnvironment: ProductionEnvironmentResponse }>({
        query: FETCH_PRODUCTION_ENVIRONMENT,
        variables: { projectId },
        fetchPolicy: 'network-only',
      })
      .pipe(map((result) => result.data?.fetchProductionEnvironment!));
  }

  generateProductionConfig(projectId: string): Observable<ProductionEnvironmentResponse> {
    const GENERATE_PRODUCTION_CONFIG = gql`
      mutation GenerateProductionConfig($projectId: String!) {
        generateProductionConfig(project_id: $projectId) {
          success
          compose_path
          error
          message
        }
      }
    `;

    return this.apollo
      .mutate<{ generateProductionConfig: any }>({
        mutation: GENERATE_PRODUCTION_CONFIG,
        variables: { projectId },
      })
      .pipe(
        map((result) => {
          const response = result.data?.generateProductionConfig;
          return {
            success: response.success,
            data: {
              compose_file: response.compose_path,
              // Other fields will be reloaded via loadProductionEnvironment effect
            } as any,
            error: response.error,
            message: response.message
          };
        })
      );
  }
  /**
   * Generate C4 Context Diagram
   */
  generateC4Diagram(architecture: ProjectArchitecture): string {
    const lines: string[] = [];

    lines.push('C4Context');
    lines.push(
      `  title Architectural Diagram for ${architecture.project_name}`
    );
    lines.push('');

    lines.push(`  System_Boundary(system, "${architecture.project_name}") {`);

    const componentsByType = this.groupComponentsByType(
      architecture.components
    );

    for (const [type, components] of Object.entries(componentsByType)) {
      for (const comp of components) {
        const techInfo = this.getTechnologyInfo(
          comp,
          architecture.technologies
        );
        const description = techInfo ? `${comp.type} (${techInfo})` : comp.type;
        const c4Type = this.getC4ElementType(comp.type);
        lines.push(
          `    ${c4Type}(${comp.component_id}, "${comp.name}", "${description}")`
        );
      }
    }

    lines.push('  }');
    lines.push('');

    const externalComponents = architecture.components.filter(
      (c) => c.type === 'external'
    );
    if (externalComponents.length > 0) {
      for (const ext of externalComponents) {
        lines.push(
          `  System_Ext(${ext.component_id}, "${ext.name}", "${ext.type}")`
        );
      }
      lines.push('');
    }

    if (architecture.connections.length > 0) {
      for (const conn of architecture.connections) {
        const label = this.getConnectionLabel(conn);
        lines.push(`  Rel(${conn.source}, ${conn.target}, "${label}")`);
      }
    }

    lines.push('');
    lines.push('  UpdateRelStyle(system, system, $offsetY="-40")');

    return lines.join('\n');
  }

  /**
   * Generate C4 Container Diagram
   */
  generateC4ContainerDiagram(architecture: ProjectArchitecture): string {
    const lines: string[] = [];

    lines.push('C4Container');
    lines.push(`  title Container diagram for ${architecture.project_name}`);
    lines.push('');

    lines.push(
      `  Container_Boundary(system, "${architecture.project_name}") {`
    );

    for (const comp of architecture.components) {
      if (comp.type === 'external') continue;

      const techInfo = this.getTechnologyInfo(comp, architecture.technologies);
      const technology = techInfo || comp.technology || comp.type;

      lines.push(
        `    Container(${comp.component_id}, "${comp.name
        }", "${technology}", "${comp.framework || ''}")`
      );
    }

    lines.push('  }');
    lines.push('');

    const externalComponents = architecture.components.filter(
      (c) => c.type === 'external'
    );
    for (const ext of externalComponents) {
      lines.push(`  System_Ext(${ext.component_id}, "${ext.name}", "")`);
    }

    if (externalComponents.length > 0) {
      lines.push('');
    }

    for (const conn of architecture.connections) {
      const label = this.getConnectionLabel(conn);
      lines.push(`  Rel(${conn.source}, ${conn.target}, "${label}")`);
    }

    return lines.join('\n');
  }

  // Private helper methods
  private groupComponentsByType(
    components: Component[]
  ): Record<string, Component[]> {
    return components.reduce((acc, comp) => {
      if (!acc[comp.type]) {
        acc[comp.type] = [];
      }
      acc[comp.type].push(comp);
      return acc;
    }, {} as Record<string, Component[]>);
  }

  private getTechnologyInfo(
    component: Component,
    technologies: Technology[]
  ): string | null {
    if (component.technology) {
      const tech = technologies.find((t) => t.name === component.technology);
      if (tech) {
        return `${tech.name} ${tech.version !== 'latest' ? tech.version : ''
          }`.trim();
      }
      return component.technology;
    }
    return null;
  }

  private getC4ElementType(componentType: string): string {
    const typeMap: Record<string, string> = {
      database: 'ContainerDb',
      cache: 'ContainerQueue',
      api: 'Container',
      web: 'Container',
      gateway: 'Container',
      queue: 'ContainerQueue',
      service: 'Container',
    };

    return typeMap[componentType] || 'Container';
  }

  private getConnectionLabel(connection: Connection): string {
    const parts: string[] = [];

    if (connection.type) {
      parts.push(connection.type.toUpperCase());
    }

    if (connection.port) {
      parts.push(`port ${connection.port}`);
    }

    return parts.length > 0 ? parts.join(' - ') : 'uses';
  }

  private parseEnvironmentVariables(
    env: string
  ): Array<{ name: string; value: string }> | null {
    if (!env) return null;

    return env
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item.includes('='))
      .map((item) => {
        const [name, ...valueParts] = item.split('=');
        const value = valueParts.join('=');
        return { name: name.trim(), value: value.trim() };
      });
  }

  private mapTechnologyTypeToCategory(type: string): TechnologyCategory {
    const typeLower = type.toLowerCase();
    switch (typeLower) {
      case 'database':
        return TechnologyCategory.DATABASE;
      case 'runtime':
      case 'node':
      case 'python':
      case 'java':
        return TechnologyCategory.RUNTIME;
      case 'cache':
      case 'redis':
      case 'memcached':
        return TechnologyCategory.CACHE;
      case 'queue':
      case 'rabbitmq':
      case 'kafka':
        return TechnologyCategory.QUEUE;
      case 'service':
        return TechnologyCategory.SERVICE;
      default:
        return TechnologyCategory.RUNTIME;
    }
  }

  private mapComponentToType(type?: string): ComponentTypeInput {
    if (!type) return ComponentTypeInput.EXTERNAL;

    const typeUpper = type.toUpperCase();
    switch (typeUpper) {
      case 'DATABASE':
        return ComponentTypeInput.DATABASE;
      case 'CACHE':
        return ComponentTypeInput.CACHE;
      case 'API':
        return ComponentTypeInput.API;
      case 'WEB':
        return ComponentTypeInput.WEB;
      case 'GATEWAY':
        return ComponentTypeInput.GATEWAY;
      case 'EXTERNAL':
        return ComponentTypeInput.EXTERNAL;
      default:
        const typeLower = type.toLowerCase();
        if (typeLower.includes('api')) return ComponentTypeInput.API;
        if (typeLower.includes('web')) return ComponentTypeInput.WEB;
        if (typeLower.includes('gateway')) return ComponentTypeInput.GATEWAY;
        if (typeLower.includes('database') || typeLower.includes('db'))
          return ComponentTypeInput.DATABASE;
        if (typeLower.includes('cache')) return ComponentTypeInput.CACHE;
        return ComponentTypeInput.EXTERNAL;
    }
  }

  private transformToFullProjectInput(data: any, chatId: string) {
    return {
      project: {
        name: data.project.name,
        author: data.project.author,
        description: data.project.description,
        version: data.project.version || '1.0.0',
        status: 'created',
        chatId: chatId,
        metadata: null,
      },
      technologies:
        data.technologies?.map((tech: any) => ({
          name: tech.name,
          version: tech.version || 'latest',
          category: this.mapTechnologyTypeToCategory(tech.type),
          port: null,
          environmentVariables: this.parseEnvironmentVariables(
            tech.environment_variables as string
          ),
          configuration: null,
          enabled: true,
        })) || [],
      components:
        data.components?.map((component: any) => ({
          componentId: component.component_id,
          name: component.name,
          type: this.mapComponentToType(component.type),
          technology: component.technology,
          framework: component.framework,
          port: component.port || null,
          environmentVariables: component.environment_variables || null,
          dependencies: component.dependencies || [],
        })) || [],
      connections:
        data.connections?.map((connection: any) => ({
          source: connection.source,
          target: connection.target,
          type: connection.type || 'api',
          port: connection.port || null,
        })) || [],
    };
  }
}
