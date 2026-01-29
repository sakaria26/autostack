// mongo-init/01-init-autostack-db.js
// This script runs when MongoDB container starts for the first time

// Switch to the autostack database
db = db.getSiblingDB('autostack');

// Create a user for the autostack database
db.createUser({
  user: 'adminmongo',
  pwd: 'password123',
  roles: [
    {
      role: 'readWrite',
      db: 'autostack'
    }
  ]
});

// Create collections
db.createCollection('project_configs');
db.createCollection('migrations');

// Create indexes
db.project_configs.createIndex({ "project.name": 1 }, { unique: true });
db.project_configs.createIndex({ "created_at": -1 });
db.migrations.createIndex({ "version": 1 }, { unique: true });

print('AutoStack database initialized successfully!');