import { createActionGroup, emptyProps, props } from '@ngrx/store';
import {
  GitInfo,
  ProductionEnvironment,
  ProjectArchitecture,
  ProjectResult,
} from '../../services/project/project-service';

export const ProjectActions = createActionGroup({
  source: 'Project',
  events: {
    // Load All Projects
    'Load Projects': emptyProps(),
    'Load Projects Success': props<{ projects: ProjectResult[] }>(),
    'Load Projects Failure': props<{ error: string }>(),

    // Load Single Project
    'Load Project': props<{ projectId: string }>(),
    'Load Project Success': props<{ project: ProjectResult }>(),
    'Load Project Failure': props<{ error: string }>(),

    // Load Project Architecture (full details with components, connections, technologies)
    'Load Project Architecture': props<{ projectId: string }>(),
    'Load Project Architecture Success': props<{
      architecture: ProjectArchitecture;
    }>(),
    'Load Project Architecture Failure': props<{ error: string }>(),

    // Create Project from Schema
    'Create Project': props<{ schema: any; chatId: string }>(),
    'Create Project Success': props<{ projectId: string; message: string }>(),
    'Create Project Failure': props<{ error: string }>(),

    'Initialise Repository': props<{ projectId: string }>(),
    'Initialise Repository Success': props<{
      projectId: string;
      gitInfo: GitInfo;
    }>(),
    'Initialise Repository Failure': props<{ error: string }>(),

    'Delete Component': props<{ componentId: string }>(),
    'Delete Component Success': emptyProps(),
    'Delete Component Failure': props<{ error: string }>(),

    'Load Production Environment': props<{ projectId: string }>(),
    'Load Production Environment Success': props<{
      productionEnvironment: ProductionEnvironment;
    }>(),
    'Load Production Environment Failure': props<{ error: string }>(),

    'Generate Production Config': props<{ projectId: string }>(),
    'Generate Production Config Success': props<{ projectId: string; message: string; composePath: string }>(),
    'Generate Production Config Failure': props<{ error: string }>(),

    // Set Current Project (for navigation/selection)
    'Set Current Project': props<{ projectId: string }>(),

    // Set Project Details (legacy - for direct setting)
    'Set Project Details': props<{ project: ProjectResult }>(),

    'Update Project': props<{
      projectId: string;
      updates: {
        name?: string;
        author?: string;
        description?: string;
        version?: string;
        tags?: string[];
      };
    }>(),
    'Update Project Success': props<{
      projectId: string;
      message: string;
      updates: any; // The updates that were applied
    }>(),
    'Update Project Failure': props<{ error: string }>(),

    // Reset State
    'Reset Project State': emptyProps(),
  },
});
