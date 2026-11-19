mock_provider "openstack" {
  override_resource {
    target = openstack_networking_network_v2.main
    values = { id = "networking_network_v2-main" }
  }
  override_resource {
    target = openstack_networking_subnet_v2.public
    values = { id = "networking_subnet_v2-public" }
  }
  override_resource {
    target = openstack_networking_subnet_v2.app
    values = { id = "networking_subnet_v2-app" }
  }
  override_resource {
    target = openstack_networking_subnet_v2.db
    values = { id = "networking_subnet_v2-db" }
  }
  override_resource {
    target = openstack_networking_router_v2.router
    values = { id = "networking_router_v2-router" }
  }
  override_resource {
    target = openstack_networking_router_interface_v2.public
    values = { id = "networking_router_interface_v2-public" }
  }
  override_resource {
    target = openstack_networking_router_interface_v2.app
    values = { id = "networking_router_interface_v2-app" }
  }
  override_resource {
    target = openstack_networking_secgroup_v2.app
    values = { id = "networking_secgroup_v2-app" }
  }
  override_resource {
    target = openstack_networking_secgroup_v2.db
    values = { id = "networking_secgroup_v2-db" }
  }
  override_resource {
    target = openstack_networking_secgroup_rule_v2.app_from_lb
    values = { id = "networking_secgroup_rule_v2-app_from_lb" }
  }
  override_resource {
    target = openstack_networking_secgroup_rule_v2.db_from_app
    values = { id = "networking_secgroup_rule_v2-db_from_app" }
  }
  override_resource {
    target = openstack_objectstorage_container_v1.media
    values = { id = "objectstorage_container_v1-media" }
  }
  override_resource {
    target = openstack_networking_port_v2.app[0]
    values = { id = "networking_port_v2-app0", all_fixed_ips = ["10.0.10.10"] }
  }
  override_resource {
    target = openstack_networking_port_v2.app[1]
    values = { id = "networking_port_v2-app1", all_fixed_ips = ["10.0.10.11"] }
  }
  override_resource {
    target = openstack_compute_instance_v2.app[0]
    values = { id = "compute_instance_v2-app0" }
  }
  override_resource {
    target = openstack_compute_instance_v2.app[1]
    values = { id = "compute_instance_v2-app1" }
  }
  override_resource {
    target = openstack_lb_loadbalancer_v2.web
    values = { id = "lb_loadbalancer_v2-web", vip_port_id = "port-vip" }
  }
  override_resource {
    target = openstack_lb_listener_v2.http
    values = { id = "lb_listener_v2-http" }
  }
  override_resource {
    target = openstack_lb_pool_v2.app
    values = { id = "lb_pool_v2-app" }
  }
  override_resource {
    target = openstack_lb_monitor_v2.http
    values = { id = "lb_monitor_v2-http" }
  }
  override_resource {
    target = openstack_lb_member_v2.app[0]
    values = { id = "lb_member_v2-app0" }
  }
  override_resource {
    target = openstack_lb_member_v2.app[1]
    values = { id = "lb_member_v2-app1" }
  }
  override_resource {
    target = openstack_networking_floatingip_v2.lb
    values = { id = "networking_floatingip_v2-lb" }
  }
  override_resource {
    target = openstack_networking_floatingip_associate_v2.lb
    values = { id = "networking_floatingip_associate_v2-lb" }
  }
  override_resource {
    target = openstack_networking_port_v2.db
    values = { id = "networking_port_v2-db", all_fixed_ips = ["10.0.20.10"] }
  }
  override_resource {
    target = openstack_db_instance_v1.db
    values = { id = "db_instance_v1-db" }
  }
}
variables { db_password = "test-only" }
run "conformance" {
  command = apply
  assert {
    condition     = openstack_networking_network_v2.main.admin_state_up
    error_message = "R01 private tenant network"
  }
  assert {
    condition     = length(distinct([openstack_networking_subnet_v2.public.cidr, openstack_networking_subnet_v2.app.cidr, openstack_networking_subnet_v2.db.cidr])) == 3 && length(distinct(openstack_compute_instance_v2.app[*].availability_zone)) == 2
    error_message = "R02 three tiers; app instances in two availability zones"
  }
  assert {
    condition     = openstack_networking_router_v2.router.external_network_id == data.openstack_networking_network_v2.external.id && openstack_networking_floatingip_associate_v2.lb.port_id == openstack_lb_loadbalancer_v2.web.vip_port_id && openstack_networking_router_interface_v2.public.subnet_id == openstack_networking_subnet_v2.public.id
    error_message = "R03 public entry point via external gateway and floating IP"
  }
  assert {
    condition     = openstack_networking_router_v2.router.enable_snat && openstack_networking_router_interface_v2.app.subnet_id == openstack_networking_subnet_v2.app.id
    error_message = "R04 app tier private with source NAT"
  }
  assert {
    condition     = openstack_networking_secgroup_rule_v2.app_from_lb.port_range_min == 80 && openstack_networking_secgroup_rule_v2.app_from_lb.remote_ip_prefix == openstack_networking_subnet_v2.public.cidr && openstack_networking_secgroup_rule_v2.app_from_lb.security_group_id == openstack_networking_secgroup_v2.app.id && openstack_networking_secgroup_rule_v2.db_from_app.remote_group_id == openstack_networking_secgroup_v2.app.id && openstack_networking_secgroup_rule_v2.db_from_app.port_range_min == 3306 && alltrue([for p in openstack_networking_port_v2.app : contains(tolist(p.security_group_ids), openstack_networking_secgroup_v2.app.id)]) && toset(openstack_networking_port_v2.db.security_group_ids) == toset([openstack_networking_secgroup_v2.db.id])
    error_message = "R05 app<-LB subnet:80 attached to app ports; db<-app:3306 attached to the database port"
  }
  assert {
    condition     = openstack_objectstorage_container_v1.media.container_read == null || openstack_objectstorage_container_v1.media.container_read == ""
    error_message = "R07 container has no public read ACL"
  }
  assert {
    condition     = alltrue([for i in openstack_compute_instance_v2.app : strcontains(i.user_data, "/var/www/html/health")])
    error_message = "R08 instances boot a web server that serves /health"
  }
  assert {
    condition     = length(openstack_compute_instance_v2.app) == 2
    error_message = "R09 fixed pool of two instances (no autoscaling resource)"
  }
  assert {
    condition     = openstack_lb_monitor_v2.http.url_path == "/health" && openstack_lb_monitor_v2.http.expected_codes == "200" && openstack_lb_monitor_v2.http.pool_id == openstack_lb_pool_v2.app.id && openstack_lb_pool_v2.app.listener_id == openstack_lb_listener_v2.http.id && openstack_lb_listener_v2.http.protocol_port == 80 && length(openstack_lb_member_v2.app) == 2 && alltrue([for m in openstack_lb_member_v2.app : m.pool_id == openstack_lb_pool_v2.app.id && m.protocol_port == 80])
    error_message = "R10 L7 LB on :80 with /health probe and two members"
  }
  assert {
    condition     = one([for d in openstack_db_instance_v1.db.datastore : d.type]) == "mysql" && one([for d in openstack_db_instance_v1.db.datastore : d.version]) == "8.0" && one([for n in openstack_db_instance_v1.db.network : n.port]) == openstack_networking_port_v2.db.id && one([for f in openstack_networking_port_v2.db.fixed_ip : f.subnet_id]) == openstack_networking_subnet_v2.db.id
    error_message = "R11 private MySQL 8.0 on the db subnet (single instance; HA and backup policy not expressible)"
  }
}
