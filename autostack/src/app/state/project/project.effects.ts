import { Injectable, inject } from '@angular/core';
import { Router } from '@angular/router';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { of } from 'rxjs';
import { catchError, map, switchMap, tap } from 'rxjs/operators';

import { ProjectService } from '../../services/project/project-service';
import { ProjectActions } from './project.actions';

@Injectable()
export class ProjectEffects {
  private actions$ = inject(Actions);
  private projectService = inject(ProjectService);
  private router = inject(Router);

  // Load all projects
  loadProjects$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.loadProjects),
      switchMap(() =>
        this.projectService.fetchAllProjects().pipe(
          map((result) => {
            if (result && Array.isArray(result)) {
              return ProjectActions.loadProjectsSuccess({
                projects: result,
              });
            } else if (result) {
              // Single project returned, wrap in array
              return ProjectActions.loadProjectsSuccess({
                projects: [result],
              });
            } else {
              return ProjectActions.loadProjectsFailure({
                error: 'No projects found',
              });
            }
          }),
          catchError((error) =>
            of(
              ProjectActions.loadProjectsFailure({
                error: error.message || 'Failed to load projects',
              })
            )
          )
        )
      )
    )
  );

  // Load single project (basic info only)
  loadProject$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.loadProject),
      switchMap(({ projectId }) =>
        this.projectService.fetchProjectById(projectId).pipe(
          map((project) => {
            if (project) {
              return ProjectActions.loadProjectSuccess({ project });
            } else {
              return ProjectActions.loadProjectFailure({
                error: 'Project not found',
              });
            }
          }),
          catchError((error) =>
            of(
              ProjectActions.loadProjectFailure({
                error: error.message || 'Failed to load project',
              })
            )
          )
        )
      )
    )
  );

  // Load project architecture (full details)
  loadProjectArchitecture$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.loadProjectArchitecture),
      switchMap(({ projectId }) =>
        this.projectService.fetchProjectArchitecture(projectId).pipe(
          map((architecture) => {
            if (architecture) {
              return ProjectActions.loadProjectArchitectureSuccess({
                architecture,
              });
            } else {
              return ProjectActions.loadProjectArchitectureFailure({
                error: 'Architecture not found',
              });
            }
          }),
          catchError((error) =>
            of(
              ProjectActions.loadProjectArchitectureFailure({
                error: error.message || 'Failed to load project architecture',
              })
            )
          )
        )
      )
    )
  );

  // Create project from schema
  createProject$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.createProject),
      switchMap(({ schema, chatId }) =>
        this.projectService.createFullProject(schema, chatId).pipe(
          map((result) => {
            if (result.success && result.projectId) {
              return ProjectActions.createProjectSuccess({
                projectId: result.projectId,
                message: result.message || 'Project created successfully',
              });
            } else {
              return ProjectActions.createProjectFailure({
                error: result.error || 'Failed to create project',
              });
            }
          }),
          catchError((error) =>
            of(
              ProjectActions.createProjectFailure({
                error:
                  error.message || 'An error occurred while creating project',
              })
            )
          )
        )
      )
    )
  );

  initialiseGit$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.initialiseRepository),
      switchMap(({ projectId }) =>
        this.projectService.initialiseGit(projectId).pipe(
          map((result) => {
            if (result.success && result.git_info) {
              return ProjectActions.initialiseRepositorySuccess({
                projectId,
                gitInfo: result.git_info,
              });
            } else {
              return ProjectActions.initialiseRepositoryFailure({
                error: result.error || 'Failed to initialise repository',
              });
            }
          }),
          catchError((error) =>
            of(
              ProjectActions.initialiseRepositoryFailure({
                error: error.message || 'Failed to initialise repository',
              })
            )
          )
        )
      )
    )
  );

  reloadProjectAfterGitInit$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.initialiseRepositorySuccess),
      map(({ projectId }) => ProjectActions.loadProject({ projectId }))
    )
  );

  updateProject$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.updateProject),
      switchMap(({ projectId, updates }) =>
        this.projectService.updateProject(projectId, updates).pipe(
          map((result) => {
            if (result.success && result.projectId) {
              return ProjectActions.updateProjectSuccess({
                projectId: result.projectId,
                message: result.message || 'Project updated successfully',
                updates,
              });
            } else {
              return ProjectActions.updateProjectFailure({
                error: result.error || 'Failed to update project',
              });
            }
          }),
          catchError((error) =>
            of(
              ProjectActions.updateProjectFailure({
                error:
                  error.message || 'An error occurred while updating project',
              })
            )
          )
        )
      )
    )
  );

  navigateAfterUpdate$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.updateProjectSuccess),
      tap(({ projectId }) => {
        this.router.navigate(['/project', projectId]);
      })
    )
  );

  // Navigate to project page after successful creation
  navigateAfterCreate$ = createEffect(
    () =>
      this.actions$.pipe(
        ofType(ProjectActions.createProjectSuccess),
        tap(({ projectId }) => {
          this.router.navigate(['/project', projectId]);
        })
      ),
    { dispatch: false }
  );

  // Optionally load project details after setting current project
  loadAfterSetCurrent$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.setCurrentProject),
      switchMap(({ projectId }) =>
        of(ProjectActions.loadProject({ projectId }))
      )
    )
  );

  deleteComponent$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.deleteComponent),
      switchMap(({ componentId }) =>
        this.projectService.deleteComponent(componentId).pipe(
          map((result) => {
            if (result.success) {
              return ProjectActions.deleteComponentSuccess();
            } else {
              return ProjectActions.deleteComponentFailure({
                error: result.error || 'Failed to delete component',
              });
            }
          }),
          catchError((error) =>
            of(
              ProjectActions.deleteComponentFailure({
                error:
                  error.message || 'An error occurred while creating project',
              })
            )
          )
        )
      )
    )
  );

  loadProductionEnvironment$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.loadProductionEnvironment),
      switchMap(({ projectId }) =>
        this.projectService.fetchProductionEnvironment(projectId).pipe(
          map((result) => {
            if (result.success && result.data) {
              return ProjectActions.loadProductionEnvironmentSuccess({
                productionEnvironment: result.data,
              });
            } else {
              return ProjectActions.loadProductionEnvironmentFailure({
                error: result.error || 'Failed to load production environment',
              });
            }
          }),
          catchError((error) =>
            of(
              ProjectActions.loadProductionEnvironmentFailure({
                error: error.message || 'Failed to load production environment',
              })
            )
          )
        )
      )
    )
  );

  generateProductionConfig$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.generateProductionConfig),
      switchMap(({ projectId }) =>
        this.projectService.generateProductionConfig(projectId).pipe(
          map((result) => {
            if (result.success) {
              return ProjectActions.generateProductionConfigSuccess({
                projectId,
                message: result.message || 'Config generated successfully',
                composePath: result.data?.compose_file || ''
              });
            } else {
              return ProjectActions.generateProductionConfigFailure({
                error: result.error || 'Failed to generate config',
              });
            }
          }),
          catchError((error) =>
            of(
              ProjectActions.generateProductionConfigFailure({
                error: error.message || 'Failed to generate config',
              })
            )
          )
        )
      )
    )
  );

  reloadAfterGeneration$ = createEffect(() =>
    this.actions$.pipe(
      ofType(ProjectActions.generateProductionConfigSuccess),
      map(({ projectId }) => ProjectActions.loadProductionEnvironment({ projectId }))
    )
  );
}
