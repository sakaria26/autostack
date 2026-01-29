import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { Subscription } from 'rxjs';
import { ProjectFacade } from '../../../state/project/project.facade';

@Component({
  selector: 'app-production',
  imports: [CommonModule],
  templateUrl: './production.html',
  styleUrl: './production.scss',
})
export class Production {
  private projectFacade = inject(ProjectFacade);
  private subscriptions = new Subscription();

  projectId: string | null = null;
  productionEnvironment: any = null;
  loading = false;
  error: string | null = null;

  ngOnInit() {
    // Subscribe to current project ID
    this.subscriptions.add(
      this.projectFacade.currentProjectId$.subscribe((id) => {
        this.projectId = id;
        if (id) {
          this.loadProductionEnvironment();
        }
      })
    );

    this.subscriptions.add(
      this.projectFacade.currentProductionEnvironment$.subscribe((env) => {
        this.productionEnvironment = env;
      })
    );

    // Subscribe to loading state
    this.subscriptions.add(
      this.projectFacade.loadingProductionEnvironment$.subscribe((loading) => {
        this.loading = loading;
      })
    );

    // Subscribe to error state
    this.subscriptions.add(
      this.projectFacade.error$.subscribe((error) => {
        this.error = error;
      })
    );
  }

  loadProductionEnvironment() {
    if (this.projectId) {
      this.projectFacade.loadProductionEnvironment(this.projectId);
    }
  }

  generateComposeFile() {
    if (this.projectId) {
      this.projectFacade.generateProductionConfig(this.projectId);
    }
  }

  refresh() {
    this.loadProductionEnvironment();
  }

  getContainerStatusClass(status: string): string {
    switch (status?.toLowerCase()) {
      case 'running':
        return 'bg-green-100 text-green-800 border-green-300';
      case 'exited':
      case 'stopped':
        return 'bg-red-100 text-red-800 border-red-300';
      case 'created':
      case 'restarting':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  }

  getContainerStatusIcon(status: string): string {
    switch (status?.toLowerCase()) {
      case 'running':
        return '🟢';
      case 'exited':
      case 'stopped':
        return '🔴';
      case 'created':
      case 'restarting':
        return '🟡';
      default:
        return '⚪';
    }
  }

  getPortString(ports: any[]): string {
    if (!ports || ports.length === 0) return 'No ports';
    return ports
      .map((p) =>
        p.PublicPort ? `${p.PublicPort}:${p.PrivatePort}` : p.PrivatePort
      )
      .join(', ');
  }

  ngOnDestroy() {
    this.subscriptions.unsubscribe();
  }
}
