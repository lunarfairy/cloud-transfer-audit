
terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "8.10.0" }
  }
}
provider "google" {
  project = var.project_id
  region  = var.region
}
variable "project_id" {
  type = string
}
variable "region" {
  type    = string
  default = "australia-southeast1"
}
variable "db_password" {
  type      = string
  sensitive = true
}
locals {
  startup = "#!/bin/bash\napt-get update && apt-get install -y apache2 php\nmkdir -p /var/www/html && echo ok > /var/www/html/health\nsystemctl enable --now apache2\n"
}

# K01 virtual network (global; address space lives on regional subnets)
resource "google_compute_network" "main" {
  name                    = "ra-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

# K02 subnet (regional: spans all zones of the region)
resource "google_compute_subnetwork" "app" {
  name                     = "ra-app"
  ip_cidr_range            = "10.0.10.0/24"
  region                   = var.region
  network                  = google_compute_network.main.id
  private_ip_google_access = true
}

# K03 internet routing: default internet route is created automatically with the network

# K04 outbound-only NAT (Cloud Router + Cloud NAT)
resource "google_compute_router" "nat" {
  name    = "ra-router"
  region  = var.region
  network = google_compute_network.main.id
}
resource "google_compute_router_nat" "nat" {
  name                               = "ra-nat"
  router                             = google_compute_router.nat.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"
  subnetwork {
    name                    = google_compute_subnetwork.app.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}

# K05 traffic filtering: network-level firewall rules that select targets by network tag
resource "google_compute_firewall" "app_from_lb" {
  name          = "ra-allow-lb-http"
  network       = google_compute_network.main.id
  direction     = "INGRESS"
  priority      = 1000
  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
  target_tags   = ["app"]
  allow {
    protocol = "tcp"
    ports    = ["80"]
  }
}

# K06 workload identity (service account + bucket-scoped IAM binding)
resource "google_service_account" "app" {
  account_id   = "ra-app"
  display_name = "RA application tier"
}
resource "google_storage_bucket_iam_member" "app_rw" {
  bucket = google_storage_bucket.media.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.app.email}"
}

# K07 private object storage
resource "google_storage_bucket" "media" {
  name                        = "${var.project_id}-ra-media"
  location                    = "AUSTRALIA-SOUTHEAST1"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

# K08 compute template
resource "google_compute_instance_template" "app" {
  name_prefix             = "ra-app-"
  machine_type            = "e2-small"
  tags                    = ["app"]
  metadata_startup_script = local.startup
  disk {
    source_image = "debian-cloud/debian-12"
    auto_delete  = true
    boot         = true
  }
  network_interface {
    subnetwork = google_compute_subnetwork.app.id
  }
  service_account {
    email  = google_service_account.app.email
    scopes = ["cloud-platform"]
  }
  lifecycle {
    create_before_destroy = true
  }
}

# K09 elastic pool: regional managed instance group + autoscaler
resource "google_compute_health_check" "http" {
  name                = "ra-http-hc"
  check_interval_sec  = 10
  timeout_sec         = 5
  unhealthy_threshold = 3
  http_health_check {
    port         = 80
    request_path = "/health"
  }
}
resource "google_compute_region_instance_group_manager" "app" {
  name                      = "ra-app-mig"
  region                    = var.region
  base_instance_name        = "ra-app"
  distribution_policy_zones = ["australia-southeast1-a", "australia-southeast1-b"]
  version {
    instance_template = google_compute_instance_template.app.self_link_unique
  }
  named_port {
    name = "http"
    port = 80
  }
  auto_healing_policies {
    health_check      = google_compute_health_check.http.id
    initial_delay_sec = 120
  }
}
resource "google_compute_region_autoscaler" "app" {
  name   = "ra-app-autoscaler"
  region = var.region
  target = google_compute_region_instance_group_manager.app.id
  autoscaling_policy {
    min_replicas    = 2
    max_replicas    = 6
    cooldown_period = 60
    cpu_utilization {
      target = 0.6
    }
  }
}

# K10 layer-7 load balancer: global external Application Load Balancer (five resources)
resource "google_compute_global_address" "lb" {
  name = "ra-lb-ip"
}
resource "google_compute_backend_service" "app" {
  name                  = "ra-app-backend"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  health_checks         = [google_compute_health_check.http.id]
  enable_cdn            = true
  backend {
    group           = google_compute_region_instance_group_manager.app.instance_group
    balancing_mode  = "UTILIZATION"
    capacity_scaler = 1.0
  }
  cdn_policy {
    cache_mode = "CACHE_ALL_STATIC"
    cache_key_policy {
      include_host         = true
      include_protocol     = true
      include_query_string = false
    }
  }
}
resource "google_compute_url_map" "web" {
  name            = "ra-url-map"
  default_service = google_compute_backend_service.app.id
}
resource "google_compute_target_http_proxy" "web" {
  name    = "ra-http-proxy"
  url_map = google_compute_url_map.web.id
}
resource "google_compute_global_forwarding_rule" "web" {
  name                  = "ra-http-rule"
  target                = google_compute_target_http_proxy.web.id
  port_range            = "80"
  ip_protocol           = "TCP"
  ip_address            = google_compute_global_address.lb.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# K11 managed relational database over private services access
resource "google_compute_global_address" "sql_range" {
  name          = "ra-sql-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}
resource "google_service_networking_connection" "sql" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql_range.name]
}
resource "google_sql_database_instance" "db" {
  name                = "ra-mysql"
  region              = var.region
  database_version    = "MYSQL_8_0"
  deletion_protection = false
  settings {
    tier              = "db-custom-1-3840"
    availability_type = "REGIONAL"
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
    }
    backup_configuration {
      enabled            = true
      binary_log_enabled = true
      backup_retention_settings {
        retained_backups = 7
      }
    }
  }
  depends_on = [google_service_networking_connection.sql]
}
resource "google_sql_user" "app" {
  name     = "appadmin"
  instance = google_sql_database_instance.db.name
  password = var.db_password
}

# K12 content delivery: Cloud CDN is a property of the backend service (enable_cdn, cdn_policy above)

# K13 metric alarm
resource "google_monitoring_alert_policy" "cpu_high" {
  display_name = "ra-cpu-high"
  combiner     = "OR"
  conditions {
    display_name = "CPU above 80 percent"
    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"compute.googleapis.com/instance/cpu/utilization\" AND metadata.system_labels.\"instance_group\" = \"ra-app-mig\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
}
