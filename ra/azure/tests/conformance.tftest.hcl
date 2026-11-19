mock_provider "azurerm" {
  override_resource {
    target = azurerm_resource_group.rg
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg" }
  }
  override_resource {
    target = azurerm_virtual_network.main
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/virtualNetworks/ra-vnet" }
  }
  override_resource {
    target = azurerm_subnet.public
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/virtualNetworks/ra-vnet/subnets/ra-appgw" }
  }
  override_resource {
    target = azurerm_subnet.app
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/virtualNetworks/ra-vnet/subnets/ra-app" }
  }
  override_resource {
    target = azurerm_subnet.db
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/virtualNetworks/ra-vnet/subnets/ra-db" }
  }
  override_resource {
    target = azurerm_public_ip.nat
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/publicIPAddresses/ra-nat-ip", ip_address = "203.0.113.11" }
  }
  override_resource {
    target = azurerm_public_ip.appgw
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/publicIPAddresses/ra-appgw-ip", ip_address = "203.0.113.10" }
  }
  override_resource {
    target = azurerm_nat_gateway.nat
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/natGateways/ra-nat" }
  }
  override_resource {
    target = azurerm_network_security_group.app
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/networkSecurityGroups/ra-app-nsg" }
  }
  override_resource {
    target = azurerm_network_security_group.db
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/networkSecurityGroups/ra-db-nsg" }
  }
  override_resource {
    target = azurerm_user_assigned_identity.app
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/ra-app-identity", principal_id = "11111111-2222-3333-4444-555555555555" }
  }
  override_resource {
    target = azurerm_storage_account.media
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Storage/storageAccounts/ramediatest" }
  }
  override_resource {
    target = azurerm_storage_container.media
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Storage/storageAccounts/ramediatest/blobServices/default/containers/media" }
  }
  override_resource {
    target = azurerm_linux_virtual_machine_scale_set.app
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Compute/virtualMachineScaleSets/ra-app-vmss" }
  }
  override_resource {
    target = azurerm_application_gateway.web
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/applicationGateways/ra-appgw" }
  }
  override_resource {
    target = azurerm_private_dns_zone.db
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/privateDnsZones/ra.mysql.database.azure.com" }
  }
  override_resource {
    target = azurerm_private_dns_zone_virtual_network_link.db
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Network/privateDnsZones/ra.mysql.database.azure.com/virtualNetworkLinks/ra-db-link" }
  }
  override_resource {
    target = azurerm_mysql_flexible_server.db
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.DBforMySQL/flexibleServers/ra-mysql-test" }
  }
  override_resource {
    target = azurerm_cdn_frontdoor_profile.cdn
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Cdn/profiles/ra-fd" }
  }
  override_resource {
    target = azurerm_cdn_frontdoor_endpoint.cdn
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Cdn/profiles/ra-fd/afdEndpoints/ra-fd-endpoint" }
  }
  override_resource {
    target = azurerm_cdn_frontdoor_origin_group.cdn
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Cdn/profiles/ra-fd/originGroups/ra-origins" }
  }
  override_resource {
    target = azurerm_cdn_frontdoor_origin.appgw
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Cdn/profiles/ra-fd/originGroups/ra-origins/origins/appgw" }
  }
  override_resource {
    target = azurerm_monitor_autoscale_setting.app
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Insights/autoScaleSettings/ra-app-autoscale" }
  }
  override_resource {
    target = azurerm_monitor_metric_alert.cpu_high
    values = { id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ra-rg/providers/Microsoft.Insights/metricAlerts/ra-cpu-high" }
  }
}
variables {
  subscription_id = "00000000-0000-0000-0000-000000000000"
  db_password     = "Test-only-Passw0rd!"
  ssh_public_key  = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDV1L/459aZ4cnpeW5TfadUFLSkJMi6SjJbC10fVybFsw9nGX4lNiKeDhNpaA4Tgt8ATVlOG8pCrENal6jV4hg912mSDuOo4qzf42t6i7vMlUYYQ0yfm3k0xqysVpkvwN62jFvsQdJ+W3MeS2Q9bTc6YkTDO6hLFAsfkQOv0h91isI1bDB0utmngTAkkZBpWz+u1IQVN6IYSIxSJPsu7X+0bgjLGNSbTEkvEy5UHj4vXzsIhJa1iFrXdoqLRx947E+pMtd/KYhalSw+vL4NFR4es4vITz/Au/mv8Fv1aYqyt8lV9wD6/lows/Q4ABpzGlyRkIcKlAzffo0CPi1sB4yD test-only"
}
run "conformance" {
  command = apply
  assert {
    condition     = toset(azurerm_virtual_network.main.address_space) == toset(["10.0.0.0/16"])
    error_message = "R01 private address space"
  }
  assert {
    condition     = length(distinct(concat(azurerm_subnet.public.address_prefixes, azurerm_subnet.app.address_prefixes, azurerm_subnet.db.address_prefixes))) == 3 && toset(azurerm_linux_virtual_machine_scale_set.app.zones) == toset(["1", "2"]) && toset(azurerm_application_gateway.web.zones) == toset(["1", "2"]) && azurerm_mysql_flexible_server.db.high_availability[0].standby_availability_zone != azurerm_mysql_flexible_server.db.zone
    error_message = "R02 three tiers, each in two failure domains"
  }
  assert {
    condition     = one([for f in azurerm_application_gateway.web.frontend_ip_configuration : f.public_ip_address_id]) == azurerm_public_ip.appgw.id
    error_message = "R03 public tier reachable from the internet (system routes)"
  }
  assert {
    condition     = azurerm_subnet_nat_gateway_association.app.subnet_id == azurerm_subnet.app.id && azurerm_subnet_nat_gateway_association.app.nat_gateway_id == azurerm_nat_gateway.nat.id && azurerm_nat_gateway_public_ip_association.nat.public_ip_address_id == azurerm_public_ip.nat.id && !azurerm_subnet.app.default_outbound_access_enabled
    error_message = "R04 app tier private with outbound-only NAT"
  }
  assert {
    condition     = azurerm_network_security_rule.app_from_lb.access == "Allow" && azurerm_network_security_rule.app_from_lb.destination_port_range == "80" && azurerm_network_security_rule.app_from_lb.source_address_prefix == azurerm_subnet.public.address_prefixes[0] && azurerm_network_security_rule.app_deny_vnet.access == "Deny" && azurerm_network_security_rule.app_deny_vnet.priority > azurerm_network_security_rule.app_from_lb.priority && azurerm_network_security_rule.db_from_app.destination_port_range == "3306" && azurerm_network_security_rule.db_from_app.source_address_prefix == azurerm_subnet.app.address_prefixes[0] && azurerm_network_security_rule.db_deny_vnet.priority > azurerm_network_security_rule.db_from_app.priority && azurerm_subnet_network_security_group_association.app.subnet_id == azurerm_subnet.app.id && azurerm_subnet_network_security_group_association.app.network_security_group_id == azurerm_network_security_group.app.id && azurerm_subnet_network_security_group_association.db.subnet_id == azurerm_subnet.db.id && azurerm_subnet_network_security_group_association.db.network_security_group_id == azurerm_network_security_group.db.id
    error_message = "R05 app<-LB subnet:80, db<-app subnet:3306, explicit lower-priority denies, NSGs attached"
  }
  assert {
    condition     = azurerm_role_assignment.bucket_rw.scope == azurerm_storage_container.media.id && azurerm_role_assignment.bucket_rw.principal_id == azurerm_user_assigned_identity.app.principal_id && azurerm_role_assignment.bucket_rw.role_definition_name == "Storage Blob Data Contributor" && contains(tolist(azurerm_linux_virtual_machine_scale_set.app.identity[0].identity_ids), azurerm_user_assigned_identity.app.id)
    error_message = "R06 workload identity with container-scoped data access"
  }
  assert {
    condition     = azurerm_storage_container.media.container_access_type == "private" && !azurerm_storage_account.media.allow_nested_items_to_be_public && azurerm_storage_container.media.storage_account_id == azurerm_storage_account.media.id
    error_message = "R07 object storage not publicly accessible"
  }
  assert {
    condition     = strcontains(base64decode(azurerm_linux_virtual_machine_scale_set.app.custom_data), "/var/www/html/health")
    error_message = "R08 template boots a web server that serves /health"
  }
  assert {
    condition     = azurerm_monitor_autoscale_setting.app.target_resource_id == azurerm_linux_virtual_machine_scale_set.app.id && azurerm_monitor_autoscale_setting.app.profile[0].capacity[0].minimum == 2 && azurerm_monitor_autoscale_setting.app.profile[0].capacity[0].maximum == 6 && azurerm_monitor_autoscale_setting.app.profile[0].rule[0].metric_trigger[0].metric_name == "Percentage CPU" && azurerm_monitor_autoscale_setting.app.profile[0].rule[0].metric_trigger[0].threshold == 60 && azurerm_monitor_autoscale_setting.app.profile[0].rule[0].scale_action[0].direction == "Increase"
    error_message = "R09 elastic pool 2-6, CPU-driven scaling at 60"
  }
  assert {
    condition     = one([for p in azurerm_application_gateway.web.probe : p.path]) == "/health" && one(flatten([for p in azurerm_application_gateway.web.probe : p.match[0].status_code])) == "200" && one([for b in azurerm_application_gateway.web.backend_http_settings : b.probe_name]) == "health" && one([for l in azurerm_application_gateway.web.frontend_port : l.port]) == 80 && length(setintersection(toset(azurerm_linux_virtual_machine_scale_set.app.network_interface[0].ip_configuration[0].application_gateway_backend_address_pool_ids), toset([for p in azurerm_application_gateway.web.backend_address_pool : p.id]))) == 1
    error_message = "R10 internet-facing L7 LB on :80 with /health probe, pool membership wired"
  }
  assert {
    condition     = azurerm_mysql_flexible_server.db.version == "8.0.21" && azurerm_mysql_flexible_server.db.delegated_subnet_id == azurerm_subnet.db.id && azurerm_mysql_flexible_server.db.private_dns_zone_id == azurerm_private_dns_zone.db.id && azurerm_mysql_flexible_server.db.high_availability[0].mode == "ZoneRedundant" && azurerm_mysql_flexible_server.db.backup_retention_days == 7
    error_message = "R11 private, highly available MySQL 8.0 with 7-day backups"
  }
  assert {
    condition     = azurerm_cdn_frontdoor_origin.appgw.host_name == azurerm_public_ip.appgw.ip_address && contains(tolist(azurerm_cdn_frontdoor_route.cdn.cdn_frontdoor_origin_ids), azurerm_cdn_frontdoor_origin.appgw.id)
    error_message = "R12 CDN fronts the load balancer"
  }
  assert {
    condition     = contains(tolist(azurerm_monitor_metric_alert.cpu_high.scopes), azurerm_linux_virtual_machine_scale_set.app.id) && one([for c in azurerm_monitor_metric_alert.cpu_high.criteria : c.threshold]) == 80 && one([for c in azurerm_monitor_metric_alert.cpu_high.criteria : c.metric_name]) == "Percentage CPU" && one([for c in azurerm_monitor_metric_alert.cpu_high.criteria : c.operator]) == "GreaterThan"
    error_message = "R13 CPU alarm (>80) scoped to the pool"
  }
}
