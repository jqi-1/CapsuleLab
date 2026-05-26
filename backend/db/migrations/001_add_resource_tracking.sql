-- Add resource tracking tables for historical monitoring
CREATE TABLE IF NOT EXISTS resource_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    cpu_percent REAL,
    memory_used_mb REAL,
    memory_total_mb REAL,
    memory_percent REAL,
    disk_used_gb REAL,
    disk_total_gb REAL,
    disk_percent REAL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS container_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    container_name TEXT NOT NULL,
    cpu_percent REAL,
    memory_used_mb REAL,
    memory_limit_mb REAL,
    memory_percent REAL,
    network_rx_bytes REAL,
    network_tx_bytes REAL,
    block_read_bytes REAL,
    block_write_bytes REAL,
    FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots(id)
);

CREATE TABLE IF NOT EXISTS app_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    app_id TEXT NOT NULL,
    app_name TEXT NOT NULL,
    cpu_percent REAL,
    memory_used_mb REAL,
    memory_limit_mb REAL,
    memory_percent REAL,
    FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots(id)
);

CREATE TABLE IF NOT EXISTS compose_service_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    service_name TEXT NOT NULL,
    cpu_percent REAL,
    memory_used_mb REAL,
    memory_limit_mb REAL,
    memory_percent REAL,
    network_rx_bytes REAL,
    network_tx_bytes REAL,
    health_status TEXT,
    FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots(id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_resource_snapshots_project_id ON resource_snapshots(project_id);
CREATE INDEX IF NOT EXISTS idx_resource_snapshots_timestamp ON resource_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_container_resources_snapshot_id ON container_resources(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_app_resources_snapshot_id ON app_resources(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_compose_service_resources_snapshot_id ON compose_service_resources(snapshot_id);