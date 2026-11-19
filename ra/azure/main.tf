
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "5.12.0" }
  }
}
provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}
variable "subscription_id" {
  type = string
}
variable "location" {
  type    = string
  default = "australiaeast"
}
variable "db_password" {
  type      = string
  sensitive = true
}
variable "ssh_public_key" {
  type = string
}
locals {
  startup = "#!/bin/bash\napt-get update && apt-get install -y apache2 php\nmkdir -p /var/www/html && echo ok > /var/www/html/health\nsystemctl enable --now apache2\n"
}

# Scaffolding: every Azure resource lives in a resource group
resource "azurerm_resource_group" "rg" {
  name     = "ra-rg"
  location = var.location
}

# K01 virtual network
resource "azurerm_virtual_network" "main" {
  name                = "ra-vnet"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = ["10.0.0.0/16"]
}

# K02 subnets (regional; zones are chosen per resource, not per subnet)
resource "azurerm_subnet" "public" {
  name                 = "ra-appgw"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.0.0/24"]
}
resource "azurerm_subnet" "app" {
  name                            = "ra-app"
  resource_group_name             = azurerm_resource_group.rg.name
  virtual_network_name            = azurerm_virtual_network.main.name
  address_prefixes                = ["10.0.10.0/24"]
  default_outbound_access_enabled = false
}
resource "azurerm_subnet" "db" {
  name                 = "ra-db"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.20.0/24"]
  delegation {
    name = "mysql"
    service_delegation {
      name    = "Microsoft.DBforMySQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# K03 internet routing: provided by Azure system routes (no resource required)

# K04 outbound-only NAT for the private app tier
resource "azurerm_public_ip" "nat" {
  name                = "ra-nat-ip"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  sku                 = "Standard"
}
resource "azurerm_nat_gateway" "nat" {
  name                = "ra-nat"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "Standard"
}
resource "azurerm_nat_gateway_public_ip_association" "nat" {
  nat_gateway_id       = azurerm_nat_gateway.nat.id
  public_ip_address_id = azurerm_public_ip.nat.id
}
resource "azurerm_subnet_nat_gateway_association" "app" {
  subnet_id      = azurerm_subnet.app.id
  nat_gateway_id = azurerm_nat_gateway.nat.id
}

# K05 traffic filtering: NSGs are attached to subnets, rules have priorities and allow/deny actions
resource "azurerm_network_security_group" "app" {
  name                = "ra-app-nsg"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}
resource "azurerm_network_security_group" "db" {
  name                = "ra-db-nsg"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}
resource "azurerm_network_security_rule" "app_from_lb" {
  name                        = "allow-http-from-appgw"
  resource_group_name         = azurerm_resource_group.rg.name
  network_security_group_name = azurerm_network_security_group.app.name
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "80"
  source_address_prefix       = "10.0.0.0/24"
  destination_address_prefix  = "*"
}
resource "azurerm_network_security_rule" "app_deny_vnet" {
  name                        = "deny-other-vnet"
  resource_group_name         = azurerm_resource_group.rg.name
  network_security_group_name = azurerm_network_security_group.app.name
  priority                    = 4000
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "*"
}
resource "azurerm_network_security_rule" "db_from_app" {
  name                        = "allow-mysql-from-app"
  resource_group_name         = azurerm_resource_group.rg.name
  network_security_group_name = azurerm_network_security_group.db.name
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "3306"
  source_address_prefix       = "10.0.10.0/24"
  destination_address_prefix  = "*"
}
resource "azurerm_network_security_rule" "db_deny_vnet" {
  name                        = "deny-other-vnet"
  resource_group_name         = azurerm_resource_group.rg.name
  network_security_group_name = azurerm_network_security_group.db.name
  priority                    = 4000
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "*"
}
resource "azurerm_subnet_network_security_group_association" "app" {
  subnet_id                 = azurerm_subnet.app.id
  network_security_group_id = azurerm_network_security_group.app.id
}
resource "azurerm_subnet_network_security_group_association" "db" {
  subnet_id                 = azurerm_subnet.db.id
  network_security_group_id = azurerm_network_security_group.db.id
}

# K06 workload identity
resource "azurerm_user_assigned_identity" "app" {
  name                = "ra-app-identity"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}
resource "azurerm_role_assignment" "bucket_rw" {
  scope                = azurerm_storage_container.media.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# K07 private object storage (account + container)
resource "azurerm_storage_account" "media" {
  name                            = "ramedia${substr(md5(var.subscription_id), 0, 8)}"
  location                        = azurerm_resource_group.rg.location
  resource_group_name             = azurerm_resource_group.rg.name
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  allow_nested_items_to_be_public = false
}
resource "azurerm_storage_container" "media" {
  name                  = "media"
  storage_account_id    = azurerm_storage_account.media.id
  container_access_type = "private"
}

# K08 + K09 compute template and elastic pool are one resource (scale set)
resource "azurerm_linux_virtual_machine_scale_set" "app" {
  name                = "ra-app-vmss"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Standard_B1s"
  instances           = 2
  zones               = ["1", "2"]
  admin_username      = "azureuser"
  custom_data         = base64encode(local.startup)
  upgrade_mode        = "Automatic"
  admin_ssh_key {
    username   = "azureuser"
    public_key = var.ssh_public_key
  }
  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }
  network_interface {
    name    = "nic"
    primary = true
    ip_configuration {
      name                                         = "ipcfg"
      primary                                      = true
      subnet_id                                    = azurerm_subnet.app.id
      application_gateway_backend_address_pool_ids = [for p in azurerm_application_gateway.web.backend_address_pool : p.id]
    }
  }
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }
}
resource "azurerm_monitor_autoscale_setting" "app" {
  name                = "ra-app-autoscale"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  target_resource_id  = azurerm_linux_virtual_machine_scale_set.app.id
  profile {
    name = "default"
    capacity {
      default = 2
      minimum = 2
      maximum = 6
    }
    rule {
      metric_trigger {
        metric_name        = "Percentage CPU"
        metric_resource_id = azurerm_linux_virtual_machine_scale_set.app.id
        time_grain         = "PT1M"
        statistic          = "Average"
        time_window        = "PT5M"
        time_aggregation   = "Average"
        operator           = "GreaterThan"
        threshold          = 60
      }
      scale_action {
        direction = "Increase"
        type      = "ChangeCount"
        value     = "1"
        cooldown  = "PT5M"
      }
    }
    rule {
      metric_trigger {
        metric_name        = "Percentage CPU"
        metric_resource_id = azurerm_linux_virtual_machine_scale_set.app.id
        time_grain         = "PT1M"
        statistic          = "Average"
        time_window        = "PT5M"
        time_aggregation   = "Average"
        operator           = "LessThan"
        threshold          = 30
      }
      scale_action {
        direction = "Decrease"
        type      = "ChangeCount"
        value     = "1"
        cooldown  = "PT5M"
      }
    }
  }
}

# K10 layer-7 load balancer (Application Gateway v2, one composite resource)
resource "azurerm_public_ip" "appgw" {
  name                = "ra-appgw-ip"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = ["1", "2"]
}
resource "azurerm_application_gateway" "web" {
  name                = "ra-appgw"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  zones               = ["1", "2"]
  sku {
    name     = "Standard_v2"
    tier     = "Standard_v2"
    capacity = 2
  }
  gateway_ip_configuration {
    name      = "gwip"
    subnet_id = azurerm_subnet.public.id
  }
  frontend_ip_configuration {
    name                 = "feip"
    public_ip_address_id = azurerm_public_ip.appgw.id
  }
  frontend_port {
    name = "http"
    port = 80
  }
  http_listener {
    name                           = "http"
    frontend_ip_configuration_name = "feip"
    frontend_port_name             = "http"
    protocol                       = "Http"
  }
  backend_address_pool {
    name = "app"
  }
  probe {
    name                                      = "health"
    protocol                                  = "Http"
    path                                      = "/health"
    interval                                  = 30
    timeout                                   = 30
    unhealthy_threshold                       = 3
    pick_host_name_from_backend_http_settings = true
    match {
      status_code = ["200"]
    }
  }
  backend_http_settings {
    name                                = "app"
    cookie_based_affinity               = "Disabled"
    port                                = 80
    protocol                            = "Http"
    request_timeout                     = 30
    probe_name                          = "health"
    pick_host_name_from_backend_address = true
  }
  request_routing_rule {
    name                       = "default"
    rule_type                  = "Basic"
    priority                   = 100
    http_listener_name         = "http"
    backend_address_pool_name  = "app"
    backend_http_settings_name = "app"
  }
}

# K11 managed relational database (private access via delegated subnet + private DNS)
resource "azurerm_private_dns_zone" "db" {
  name                = "ra.mysql.database.azure.com"
  resource_group_name = azurerm_resource_group.rg.name
}
resource "azurerm_private_dns_zone_virtual_network_link" "db" {
  name                = "ra-db-link"
  private_dns_zone_id = azurerm_private_dns_zone.db.id
  virtual_network_id  = azurerm_virtual_network.main.id
}
resource "azurerm_mysql_flexible_server" "db" {
  name                   = "ra-mysql-${substr(md5(var.subscription_id), 0, 6)}"
  location               = azurerm_resource_group.rg.location
  resource_group_name    = azurerm_resource_group.rg.name
  administrator_login    = "appadmin"
  administrator_password = var.db_password
  sku_name               = "GP_Standard_D2ds_v4"
  version                = "8.0.21"
  delegated_subnet_id    = azurerm_subnet.db.id
  private_dns_zone_id    = azurerm_private_dns_zone.db.id
  backup_retention_days  = 7
  zone                   = "1"
  high_availability {
    mode                      = "ZoneRedundant"
    standby_availability_zone = "2"
  }
  storage {
    size_gb = 20
  }
  depends_on = [azurerm_private_dns_zone_virtual_network_link.db]
}

# K12 content delivery network (Front Door Standard)
resource "azurerm_cdn_frontdoor_profile" "cdn" {
  name                = "ra-fd"
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "Standard_AzureFrontDoor"
}
resource "azurerm_cdn_frontdoor_endpoint" "cdn" {
  name                     = "ra-fd-endpoint"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.cdn.id
}
resource "azurerm_cdn_frontdoor_origin_group" "cdn" {
  name                     = "ra-origins"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.cdn.id
  load_balancing {}
}
resource "azurerm_cdn_frontdoor_origin" "appgw" {
  name                           = "appgw"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.cdn.id
  host_name                      = azurerm_public_ip.appgw.ip_address
  certificate_name_check_enabled = false
  http_port                      = 80
  https_port                     = 443
}
resource "azurerm_cdn_frontdoor_route" "cdn" {
  name                          = "default"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.cdn.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.cdn.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.appgw.id]
  supported_protocols           = ["Http", "Https"]
  patterns_to_match             = ["/*"]
  forwarding_protocol           = "HttpOnly"
  https_redirect_enabled        = true
  link_to_default_domain        = true
  cache {
    query_string_caching_behavior = "IgnoreQueryString"
  }
}

# K13 metric alarm on the compute pool
resource "azurerm_monitor_metric_alert" "cpu_high" {
  name                = "ra-cpu-high"
  resource_group_name = azurerm_resource_group.rg.name
  scopes              = [azurerm_linux_virtual_machine_scale_set.app.id]
  frequency           = "PT5M"
  window_size         = "PT15M"
  criteria {
    metric_namespace = "Microsoft.Compute/virtualMachineScaleSets"
    metric_name      = "Percentage CPU"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }
}
