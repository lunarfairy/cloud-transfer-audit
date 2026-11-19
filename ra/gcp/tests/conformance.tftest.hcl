mock_provider "google" {
  override_resource {
    target = google_compute_network.main
    values = { id = "projects/test-project/global/networks/ra-vpc", self_link = "https://www.googleapis.com/compute/v1/projects/test-project/global/networks/ra-vpc" }
  }
  override_resource {
    target = google_compute_subnetwork.app
    values = { id = "projects/test-project/regions/australia-southeast1/compute_subnetwork/app" }
  }
  override_resource {
    target = google_compute_router.nat
    values = { id = "projects/test-project/regions/australia-southeast1/compute_router/nat" }
  }
  override_resource {
    target = google_compute_router_nat.nat
    values = { id = "projects/test-project/regions/australia-southeast1/compute_router_nat/nat" }
  }
  override_resource {
    target = google_compute_firewall.app_from_lb
    values = { id = "projects/test-project/regions/australia-southeast1/compute_firewall/app_from_lb" }
  }
  override_resource {
    target = google_service_account.app
    values = { id = "projects/test-project/regions/australia-southeast1/service_account/app", email = "ra-app@test-project.iam.gserviceaccount.com" }
  }
  override_resource {
    target = google_storage_bucket_iam_member.app_rw
    values = { id = "projects/test-project/regions/australia-southeast1/storage_bucket_iam_member/app_rw" }
  }
  override_resource {
    target = google_storage_bucket.media
    values = { id = "projects/test-project/regions/australia-southeast1/storage_bucket/media" }
  }
  override_resource {
    target = google_compute_instance_template.app
    values = { id = "projects/test-project/regions/australia-southeast1/compute_instance_template/app", self_link_unique = "projects/test-project/global/instanceTemplates/ra-app-x?uniqueId=1" }
  }
  override_resource {
    target = google_compute_health_check.http
    values = { id = "projects/test-project/regions/australia-southeast1/compute_health_check/http" }
  }
  override_resource {
    target = google_compute_region_instance_group_manager.app
    values = { id = "projects/test-project/regions/australia-southeast1/compute_region_instance_group_manager/app", instance_group = "projects/test-project/regions/australia-southeast1/instanceGroups/ra-app-mig" }
  }
  override_resource {
    target = google_compute_region_autoscaler.app
    values = { id = "projects/test-project/regions/australia-southeast1/compute_region_autoscaler/app" }
  }
  override_resource {
    target = google_compute_global_address.lb
    values = { id = "projects/test-project/regions/australia-southeast1/compute_global_address/lb" }
  }
  override_resource {
    target = google_compute_backend_service.app
    values = { id = "projects/test-project/regions/australia-southeast1/compute_backend_service/app" }
  }
  override_resource {
    target = google_compute_url_map.web
    values = { id = "projects/test-project/regions/australia-southeast1/compute_url_map/web" }
  }
  override_resource {
    target = google_compute_target_http_proxy.web
    values = { id = "projects/test-project/regions/australia-southeast1/compute_target_http_proxy/web" }
  }
  override_resource {
    target = google_compute_global_forwarding_rule.web
    values = { id = "projects/test-project/regions/australia-southeast1/compute_global_forwarding_rule/web" }
  }
  override_resource {
    target = google_compute_global_address.sql_range
    values = { id = "projects/test-project/regions/australia-southeast1/compute_global_address/sql_range" }
  }
  override_resource {
    target = google_service_networking_connection.sql
    values = { id = "projects/test-project/regions/australia-southeast1/service_networking_connection/sql" }
  }
  override_resource {
    target = google_sql_database_instance.db
    values = { id = "projects/test-project/regions/australia-southeast1/sql_database_instance/db" }
  }
  override_resource {
    target = google_sql_user.app
    values = { id = "projects/test-project/regions/australia-southeast1/sql_user/app" }
  }
  override_resource {
    target = google_monitoring_alert_policy.cpu_high
    values = { id = "projects/test-project/regions/australia-southeast1/monitoring_alert_policy/cpu_high" }
  }
}
variables {
  project_id  = "test-project"
  db_password = "test-only"
}
run "conformance" {
  command = apply
  assert {
    condition     = !google_compute_network.main.auto_create_subnetworks && google_compute_subnetwork.app.ip_cidr_range == "10.0.10.0/24"
    error_message = "R01 custom-mode private network"
  }
  assert {
    condition     = length(distinct(google_compute_region_instance_group_manager.app.distribution_policy_zones)) == 2 && google_sql_database_instance.db.settings[0].availability_type == "REGIONAL"
    error_message = "R02 app and db tiers in two failure domains (regional subnet)"
  }
  assert {
    condition     = google_compute_global_forwarding_rule.web.ip_address == google_compute_global_address.lb.id && google_compute_global_forwarding_rule.web.load_balancing_scheme == "EXTERNAL_MANAGED"
    error_message = "R03 public entry point reachable from the internet (default route)"
  }
  assert {
    condition     = one([for s in google_compute_router_nat.nat.subnetwork : s.name]) == google_compute_subnetwork.app.id && google_compute_router_nat.nat.router == google_compute_router.nat.name && length(google_compute_instance_template.app.network_interface[0].access_config) == 0
    error_message = "R04 app tier without public IPs, outbound-only NAT"
  }
  assert {
    condition     = google_compute_firewall.app_from_lb.direction == "INGRESS" && toset(google_compute_firewall.app_from_lb.source_ranges) == toset(["35.191.0.0/16", "130.211.0.0/22"]) && contains(tolist(google_compute_firewall.app_from_lb.target_tags), "app") && contains(tolist(google_compute_instance_template.app.tags), "app") && one(flatten([for a in google_compute_firewall.app_from_lb.allow : a.ports])) == "80"
    error_message = "R05 app<-LB proxies:80 by network tag (db reachable only via private services access)"
  }
  assert {
    condition     = google_storage_bucket_iam_member.app_rw.member == "serviceAccount:${google_service_account.app.email}" && google_storage_bucket_iam_member.app_rw.bucket == google_storage_bucket.media.name && google_storage_bucket_iam_member.app_rw.role == "roles/storage.objectUser" && google_compute_instance_template.app.service_account[0].email == google_service_account.app.email
    error_message = "R06 workload identity with bucket-scoped object access"
  }
  assert {
    condition     = google_storage_bucket.media.public_access_prevention == "enforced" && google_storage_bucket.media.uniform_bucket_level_access
    error_message = "R07 bucket not publicly accessible"
  }
  assert {
    condition     = strcontains(google_compute_instance_template.app.metadata_startup_script, "/var/www/html/health")
    error_message = "R08 template boots a web server that serves /health"
  }
  assert {
    condition     = google_compute_region_autoscaler.app.target == google_compute_region_instance_group_manager.app.id && google_compute_region_autoscaler.app.autoscaling_policy[0].min_replicas == 2 && google_compute_region_autoscaler.app.autoscaling_policy[0].max_replicas == 6 && google_compute_region_autoscaler.app.autoscaling_policy[0].cpu_utilization[0].target == 0.6 && one([for v in google_compute_region_instance_group_manager.app.version : v.instance_template]) == google_compute_instance_template.app.self_link_unique
    error_message = "R09 elastic pool 2-6, CPU target 0.6"
  }
  assert {
    condition     = google_compute_health_check.http.http_health_check[0].request_path == "/health" && contains(tolist(google_compute_backend_service.app.health_checks), google_compute_health_check.http.id) && one([for b in google_compute_backend_service.app.backend : b.group]) == google_compute_region_instance_group_manager.app.instance_group && google_compute_url_map.web.default_service == google_compute_backend_service.app.id && google_compute_target_http_proxy.web.url_map == google_compute_url_map.web.id && google_compute_global_forwarding_rule.web.target == google_compute_target_http_proxy.web.id && google_compute_global_forwarding_rule.web.port_range == "80"
    error_message = "R10 internet-facing L7 LB on :80 with /health probe"
  }
  assert {
    condition     = google_sql_database_instance.db.database_version == "MYSQL_8_0" && !google_sql_database_instance.db.settings[0].ip_configuration[0].ipv4_enabled && google_sql_database_instance.db.settings[0].ip_configuration[0].private_network == google_compute_network.main.id && google_sql_database_instance.db.settings[0].backup_configuration[0].enabled && google_sql_database_instance.db.settings[0].backup_configuration[0].backup_retention_settings[0].retained_backups == 7
    error_message = "R11 private, highly available MySQL 8.0 with 7 retained backups"
  }
  assert {
    condition     = google_compute_backend_service.app.enable_cdn
    error_message = "R12 CDN fronts the load balancer backend"
  }
  assert {
    condition     = one([for c in google_monitoring_alert_policy.cpu_high.conditions : c.condition_threshold[0].threshold_value]) == 0.8 && strcontains(one([for c in google_monitoring_alert_policy.cpu_high.conditions : c.condition_threshold[0].filter]), "instance/cpu/utilization") && strcontains(one([for c in google_monitoring_alert_policy.cpu_high.conditions : c.condition_threshold[0].filter]), "\"instance_group\" = \"${google_compute_region_instance_group_manager.app.name}\"")
    error_message = "R13 CPU alarm (>0.8 fraction) scoped to the pool"
  }
}
