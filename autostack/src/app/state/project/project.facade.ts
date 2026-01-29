import { Injectable, inject } from '@angular/core';
import { Store } from '@ngrx/store';

import { ProjectResult } from '../../services/project/project-service';
import { OperationsFacade } from '../operations/operations.facade';
import { ProjectActions } from './project.actions';
import * as ProjectSelectors from './project.selectors';

@Injectable({
  providedIn: 'root',
})
export class ProjectFacade {
  private readonly store = inject(Store);
  private readonly operationsFacade = inject(OperationsFacade);

  currentProjectId$ = this.store.select(
    ProjectSelectors.selectCurrentProjectId
  );
  currentProject$ = this.store.select(ProjectSelectors.selectCurrentProject);
  updating$ = this.store.select(ProjectSelectors.selectUpdating);
  currentArchitecture$ = this.store.select(
    ProjectSelectors.selectCurrentArchitecture
  );

  // Selectors - Current Project Details
  currentProjectName$ = this.store.select(
    ProjectSelectors.selectCurrentProjectName
  );
  currentProjectDescription$ = this.store.select(
    ProjectSelectors.selectCurrentProjectDescription
  );
  currentProjectMetadata$ = this.store.select(
    ProjectSelectors.selectCurrentProjectMetadata
  );
  currentProjectGitInfo$ = this.store.select(
    ProjectSelectors.selectCurrentProjectGitInfo
  );

  // Selectors - Architecture Details
  architectureComponents$ = this.store.select(
    ProjectSelectors.selectArchitectureComponents
  );
  architectureTechnologies$ = this.store.select(
    ProjectSelectors.selectArchitectureTechnologies
  );
  architectureConnections$ = this.store.select(
    ProjectSelectors.selectArchitectureConnections
  );
  architectureMetadata$ = this.store.select(
    ProjectSelectors.selectArchitectureMetadata
  );

  // Selectors - Projects List
  projects$ = this.store.select(ProjectSelectors.selectProjects);
  projectsCount$ = this.store.select(ProjectSelectors.selectProjectsCount);

  // Selectors - Loading States
  loading$ = this.store.select(ProjectSelectors.selectLoading);
  loadingArchitecture$ = this.store.select(
    ProjectSelectors.selectLoadingArchitecture
  );
  creating$ = this.store.select(ProjectSelectors.selectCreating);
  isLoading$ = this.store.select(ProjectSelectors.selectIsLoading);

  // Selectors - Error States
  error$ = this.store.select(ProjectSelectors.selectError);
  hasError$ = this.store.select(ProjectSelectors.selectHasError);
  hasCurrentProject$ = this.store.select(
    ProjectSelectors.selectHasCurrentProject
  );
  hasCurrentArchitecture$ = this.store.select(
    ProjectSelectors.selectHasCurrentArchitecture
  );

  currentProductionEnvironment$ = this.store.select(
    ProjectSelectors.selectCurrentProductionEnvironment
  );
  loadingProductionEnvironment$ = this.store.select(
    ProjectSelectors.selectLoadingProductionEnvironment
  );
  productionContainers$ = this.store.select(
    ProjectSelectors.selectProductionContainers
  );
  composeFileExists$ = this.store.select(
    ProjectSelectors.selectComposeFileExists
  );
  containerCount$ = this.store.select(ProjectSelectors.selectContainerCount);
  // Actions

  /**
   * Load all projects
   */
  loadProjects(): void {
    this.store.dispatch(ProjectActions.loadProjects());
  }

  /**
   * Load a specific project by ID (basic info only)
   */
  loadProject(projectId: string): void {
    this.store.dispatch(ProjectActions.loadProject({ projectId }));
  }

  /**
   * Load full project architecture (components, connections, technologies)
   */
  loadProjectArchitecture(projectId: string): void {
    this.store.dispatch(ProjectActions.loadProjectArchitecture({ projectId }));
  }

  /**
   * Create a new project from schema WITH BACKGROUND TRACKING
   * This uses the new async mutation and tracks progress via subscriptions
   *
   * The operation will be tracked in the operations panel and user can
   * continue working while the project is being created.
   */
  createProject(schema: any, chatId: string): void {
    // Use the operations facade to create with tracking
    this.operationsFacade.createProjectWithTracking(schema, chatId);
  }

  initialiseGit(projectId: string): void {
    this.store.dispatch(ProjectActions.initialiseRepository({ projectId }));
  }

  deleteComponent(componentId: string): void {
    this.store.dispatch(ProjectActions.deleteComponent({ componentId }));
  }

  /**
   * Legacy: Create project synchronously (blocks until complete)
   * Use createProject() instead for better UX
   */
  createProjectSync(schema: any, chatId: string): void {
    this.store.dispatch(ProjectActions.createProject({ schema, chatId }));
  }

  /**
   * Set the current project ID (for navigation/selection)
   * This will also trigger loading of project details
   */
  setCurrentProject(projectId: string): void {
    this.store.dispatch(ProjectActions.setCurrentProject({ projectId }));
  }

  /**
   * Set project details directly (legacy method)
   * Use this when you already have the project object
   */
  setProjectDetails(project: ProjectResult): void {
    this.store.dispatch(ProjectActions.setProjectDetails({ project }));
  }

  /**
   * Reset the project state to initial values
   */
  resetProjectState(): void {
    this.store.dispatch(ProjectActions.resetProjectState());
  }

  /**
   * Get a specific project by ID as an observable
   */
  getProjectById(projectId: string) {
    return this.store.select(ProjectSelectors.selectProjectById(projectId));
  }

  /**
   * Update project metadata
   */
  updateProject(
    projectId: string,
    updates: {
      name?: string;
      author?: string;
      description?: string;
      version?: string;
      tags?: string[];
    }
  ): void {
    this.store.dispatch(ProjectActions.updateProject({ projectId, updates }));
  }

  loadProductionEnvironment(projectId: string): void {
    this.store.dispatch(
      ProjectActions.loadProductionEnvironment({ projectId })
    );
  }

  generateProductionConfig(projectId: string): void {
    this.store.dispatch(
      ProjectActions.generateProductionConfig({ projectId })
    );
  }
}
