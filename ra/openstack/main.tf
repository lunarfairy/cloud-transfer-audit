
terraform {
  required_providers {
    openstack = { source = "terraform-provider-openstack/openstack", version = "3.4.0" }
  }
}
provider "openstack" {}
variable "external_network" {
  type    = string
  default = "public"
}
# Two failure domains for the app tier; set to the cloud's zone names (e.g. from `openstack availability zone list`).
variable "availability_zones" {
  type    = list(string)
  default = ["az1", "az2"]
}
variable "db_password" {
  type      = string
  sensitive = true
}
locals {
  startup = "#!/bin/bash\napt-get update && apt-get install -y apache2 php\nmkdir -p /var/www/html && echo ok > /var/www/html/health\nsystemctl enable --now apache2\n"
}
data "openstack_networking_network_v2" "external" {
  name = var.external_network
}

# K01 virtual network (address space lives on subnets)
resource "openstack_networking_network_v2" "main" {
  name           = "ra-net"
  admin_state_up = true
}

# K02 subnets for the load-balancer, app and db tiers
resource "openstack_networking_subnet_v2" "public" {
  name       = "ra-web"
  network_id = openstack_networking_network_v2.main.id
  cidr       = "10.0.0.0/24"
  ip_version = 4
}
resource "openstack_networking_subnet_v2" "app" {
  name       = "ra-app"
  network_id = openstack_networking_network_v2.main.id
  cidr       = "10.0.10.0/24"
  ip_version = 4
}
resource "openstack_networking_subnet_v2" "db" {
  name       = "ra-db"
  network_id = openstack_networking_network_v2.main.id
  cidr       = "10.0.20.0/24"
  ip_version = 4
}

# K03 + K04 one router provides the external gateway (floating-IP ingress) and source NAT
resource "openstack_networking_router_v2" "router" {
  name                = "ra-router"
  external_network_id = data.openstack_networking_network_v2.external.id
  enable_snat         = true
}
resource "openstack_networking_router_interface_v2" "public" {
  router_id = openstack_networking_router_v2.router.id
  subnet_id = openstack_networking_subnet_v2.public.id
}
resource "openstack_networking_router_interface_v2" "app" {
  router_id = openstack_networking_router_v2.router.id
  subnet_id = openstack_networking_subnet_v2.app.id
}

# K05 traffic filtering: security groups with group-referencing rules
resource "openstack_networking_secgroup_v2" "app" {
  name        = "ra-app"
  description = "application tier"
}
resource "openstack_networking_secgroup_v2" "db" {
  name        = "ra-db"
  description = "database tier"
}
resource "openstack_networking_secgroup_rule_v2" "app_from_lb" {
  security_group_id = openstack_networking_secgroup_v2.app.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 80
  port_range_max    = 80
  remote_ip_prefix  = "10.0.0.0/24"
}
resource "openstack_networking_secgroup_rule_v2" "db_from_app" {
  security_group_id = openstack_networking_secgroup_v2.db.id
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 3306
  port_range_max    = 3306
  remote_group_id   = openstack_networking_secgroup_v2.app.id
}

# K06 workload identity: no instance-level identity resource in this provider

# K07 private object storage (Swift container; private unless ACLs are set)
resource "openstack_objectstorage_container_v1" "media" {
  name = "ra-media"
}

# K08 + K09 compute: a fixed set of instances (no native autoscaling resource)
data "openstack_images_image_v2" "ubuntu" {
  name        = "ubuntu-24.04"
  most_recent = true
}
resource "openstack_networking_port_v2" "app" {
  count              = 2
  name               = "ra-app-${count.index}"
  network_id         = openstack_networking_network_v2.main.id
  security_group_ids = [openstack_networking_secgroup_v2.app.id]
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.app.id
  }
}
resource "openstack_compute_instance_v2" "app" {
  count             = 2
  name              = "ra-app-${count.index}"
  image_id          = data.openstack_images_image_v2.ubuntu.id
  flavor_name       = "m1.small"
  user_data         = local.startup
  availability_zone = var.availability_zones[count.index % length(var.availability_zones)]
  network {
    port = openstack_networking_port_v2.app[count.index].id
  }
}

# K10 layer-7 load balancer (Octavia)
resource "openstack_lb_loadbalancer_v2" "web" {
  name          = "ra-lb"
  vip_subnet_id = openstack_networking_subnet_v2.public.id
}
resource "openstack_lb_listener_v2" "http" {
  name            = "ra-http"
  protocol        = "HTTP"
  protocol_port   = 80
  loadbalancer_id = openstack_lb_loadbalancer_v2.web.id
}
resource "openstack_lb_pool_v2" "app" {
  name        = "ra-app"
  protocol    = "HTTP"
  lb_method   = "ROUND_ROBIN"
  listener_id = openstack_lb_listener_v2.http.id
}
resource "openstack_lb_monitor_v2" "http" {
  pool_id        = openstack_lb_pool_v2.app.id
  type           = "HTTP"
  url_path       = "/health"
  expected_codes = "200"
  delay          = 10
  timeout        = 5
  max_retries    = 3
}
resource "openstack_lb_member_v2" "app" {
  count         = 2
  pool_id       = openstack_lb_pool_v2.app.id
  address       = openstack_networking_port_v2.app[count.index].all_fixed_ips[0]
  protocol_port = 80
  subnet_id     = openstack_networking_subnet_v2.app.id
}
resource "openstack_networking_floatingip_v2" "lb" {
  pool = var.external_network
}
resource "openstack_networking_floatingip_associate_v2" "lb" {
  floating_ip = openstack_networking_floatingip_v2.lb.address
  port_id     = openstack_lb_loadbalancer_v2.web.vip_port_id
}

# K11 managed relational database (Trove), attached through a pre-created port so the db security group applies
resource "openstack_networking_port_v2" "db" {
  name               = "ra-db"
  network_id         = openstack_networking_network_v2.main.id
  security_group_ids = [openstack_networking_secgroup_v2.db.id]
  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.db.id
  }
}
resource "openstack_db_instance_v1" "db" {
  name      = "ra-mysql"
  flavor_id = "db.small"
  size        = 20
  volume_type = "standard"
  datastore {
    type    = "mysql"
    version = "8.0"
  }
  network {
    port = openstack_networking_port_v2.db.id
  }
  user {
    name      = "appadmin"
    password  = var.db_password
    databases = ["app"]
  }
  database {
    name = "app"
  }
}

# K12 content delivery and K13 metric alarm: no counterpart resources in this provider
