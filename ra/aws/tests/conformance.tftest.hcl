mock_provider "aws" {
  override_data {
    target = data.aws_availability_zones.az
    values = { names = ["ap-southeast-2a", "ap-southeast-2b", "ap-southeast-2c"] }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  override_resource {
    target = aws_vpc.main
    values = { id = "vpc-main" }
  }
  override_resource {
    target = aws_subnet.public[0]
    values = { id = "subnet-public0" }
  }
  override_resource {
    target = aws_subnet.public[1]
    values = { id = "subnet-public1" }
  }
  override_resource {
    target = aws_subnet.app[0]
    values = { id = "subnet-app0" }
  }
  override_resource {
    target = aws_subnet.app[1]
    values = { id = "subnet-app1" }
  }
  override_resource {
    target = aws_subnet.db[0]
    values = { id = "subnet-db0" }
  }
  override_resource {
    target = aws_subnet.db[1]
    values = { id = "subnet-db1" }
  }
  override_resource {
    target = aws_internet_gateway.igw
    values = { id = "internetga-igw" }
  }
  override_resource {
    target = aws_route_table.public
    values = { id = "routetable-public" }
  }
  override_resource {
    target = aws_route.public_internet
    values = { id = "route-public_internet" }
  }
  override_resource {
    target = aws_route_table_association.public[0]
    values = { id = "routetable-public0" }
  }
  override_resource {
    target = aws_route_table_association.public[1]
    values = { id = "routetable-public1" }
  }
  override_resource {
    target = aws_eip.nat
    values = { id = "eip-nat" }
  }
  override_resource {
    target = aws_nat_gateway.nat
    values = { id = "natgateway-nat" }
  }
  override_resource {
    target = aws_route_table.private
    values = { id = "routetable-private" }
  }
  override_resource {
    target = aws_route.private_nat
    values = { id = "route-private_nat" }
  }
  override_resource {
    target = aws_route_table_association.app[0]
    values = { id = "routetable-app0" }
  }
  override_resource {
    target = aws_route_table_association.app[1]
    values = { id = "routetable-app1" }
  }
  override_resource {
    target = aws_security_group.lb
    values = { id = "securitygr-lb" }
  }
  override_resource {
    target = aws_security_group.app
    values = { id = "securitygr-app" }
  }
  override_resource {
    target = aws_security_group.db
    values = { id = "securitygr-db" }
  }
  override_resource {
    target = aws_vpc_security_group_ingress_rule.lb_http
    values = { id = "vpcsecurit-lb_http" }
  }
  override_resource {
    target = aws_vpc_security_group_egress_rule.lb_to_app
    values = { id = "vpcsecurit-lb_to_app" }
  }
  override_resource {
    target = aws_vpc_security_group_ingress_rule.app_from_lb
    values = { id = "vpcsecurit-app_from_lb" }
  }
  override_resource {
    target = aws_vpc_security_group_egress_rule.app_out
    values = { id = "vpcsecurit-app_out" }
  }
  override_resource {
    target = aws_vpc_security_group_ingress_rule.db_from_app
    values = { id = "vpcsecurit-db_from_app" }
  }
  override_resource {
    target = aws_iam_role.app
    values = { id = "iamrole-app" }
  }
  override_resource {
    target = aws_iam_role_policy.bucket_rw
    values = { id = "iamrolepol-bucket_rw" }
  }
  override_resource {
    target = aws_iam_instance_profile.app
    values = { id = "iaminstanc-app" }
  }
  override_resource {
    target = aws_s3_bucket.media
    values = { id = "s3bucket-media" }
  }
  override_resource {
    target = aws_s3_bucket_public_access_block.media
    values = { id = "s3bucketpu-media" }
  }
  override_resource {
    target = aws_launch_template.app
    values = { id = "lt-0123456789abcdef0" }
  }
  override_resource {
    target = aws_autoscaling_group.app
    values = { id = "autoscalin-app" }
  }
  override_resource {
    target = aws_autoscaling_policy.cpu
    values = { id = "autoscalin-cpu" }
  }
  override_resource {
    target = aws_lb.web
    values = { id = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:loadbalancer/app/ra-alb/0123456789abcdef", arn = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:loadbalancer/app/ra-alb/0123456789abcdef", dns_name = "ra-alb-123.ap-southeast-2.elb.amazonaws.com" }
  }
  override_resource {
    target = aws_lb_target_group.app
    values = { id = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:targetgroup/ra-app-tg/0123456789abcdef", arn = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:targetgroup/ra-app-tg/0123456789abcdef" }
  }
  override_resource {
    target = aws_lb_listener.http
    values = { id = "lblistener-http" }
  }
  override_resource {
    target = aws_db_subnet_group.db
    values = { id = "dbsubnetgr-db" }
  }
  override_resource {
    target = aws_db_instance.db
    values = { id = "dbinstance-db" }
  }
  override_resource {
    target = aws_cloudfront_distribution.cdn
    values = { id = "cloudfront-cdn" }
  }
  override_resource {
    target = aws_cloudwatch_metric_alarm.cpu_high
    values = { id = "cloudwatch-cpu_high" }
  }
}
variables { db_password = "test-only" }
run "conformance" {
  command = apply
  assert {
    condition     = aws_vpc.main.cidr_block == "10.0.0.0/16"
    error_message = "R01 private address space"
  }
  assert {
    condition     = length(distinct(aws_subnet.public[*].availability_zone)) == 2 && length(distinct(aws_subnet.app[*].availability_zone)) == 2 && length(distinct(aws_subnet.db[*].availability_zone)) == 2
    error_message = "R02 three tiers, each in two failure domains"
  }
  assert {
    condition     = aws_route.public_internet.destination_cidr_block == "0.0.0.0/0" && aws_route.public_internet.gateway_id == aws_internet_gateway.igw.id && toset(aws_route_table_association.public[*].subnet_id) == toset(aws_subnet.public[*].id) && alltrue([for a in aws_route_table_association.public : a.route_table_id == aws_route_table.public.id]) && aws_route.public_internet.route_table_id == aws_route_table.public.id && aws_route.private_nat.route_table_id == aws_route_table.private.id
    error_message = "R03 public tier routed to the internet"
  }
  assert {
    condition     = aws_route.private_nat.nat_gateway_id == aws_nat_gateway.nat.id && aws_nat_gateway.nat.subnet_id == aws_subnet.public[0].id && toset(aws_route_table_association.app[*].subnet_id) == toset(aws_subnet.app[*].id) && alltrue([for a in aws_route_table_association.app : a.route_table_id == aws_route_table.private.id]) && alltrue([for s in aws_subnet.app : !coalesce(s.map_public_ip_on_launch, false)])
    error_message = "R04 app tier private with outbound-only NAT"
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.lb_http.from_port == 80 && aws_vpc_security_group_ingress_rule.lb_http.cidr_ipv4 == "0.0.0.0/0" && aws_vpc_security_group_ingress_rule.app_from_lb.referenced_security_group_id == aws_security_group.lb.id && aws_vpc_security_group_ingress_rule.app_from_lb.security_group_id == aws_security_group.app.id && aws_vpc_security_group_ingress_rule.app_from_lb.to_port == 80 && aws_vpc_security_group_ingress_rule.db_from_app.referenced_security_group_id == aws_security_group.app.id && aws_vpc_security_group_ingress_rule.db_from_app.from_port == 3306 && toset(aws_launch_template.app.vpc_security_group_ids) == toset([aws_security_group.app.id]) && toset(aws_db_instance.db.vpc_security_group_ids) == toset([aws_security_group.db.id]) && toset(aws_lb.web.security_groups) == toset([aws_security_group.lb.id])
    error_message = "R05 LB<-internet:80, app<-LB:80, db<-app:3306, groups attached"
  }
  assert {
    condition     = aws_launch_template.app.iam_instance_profile[0].name == aws_iam_instance_profile.app.name && aws_iam_instance_profile.app.role == aws_iam_role.app.name && aws_iam_role_policy.bucket_rw.role == aws_iam_role.app.id && length(data.aws_iam_policy_document.bucket_rw.statement) == 1 && toset(data.aws_iam_policy_document.bucket_rw.statement[0].actions) == toset(["s3:GetObject", "s3:PutObject"]) && alltrue([for r in data.aws_iam_policy_document.bucket_rw.statement[0].resources : endswith(r, "/*")])
    error_message = "R06 workload identity with object read/write only"
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.media.bucket == aws_s3_bucket.media.id && aws_s3_bucket_public_access_block.media.block_public_acls && aws_s3_bucket_public_access_block.media.block_public_policy && aws_s3_bucket_public_access_block.media.ignore_public_acls && aws_s3_bucket_public_access_block.media.restrict_public_buckets
    error_message = "R07 bucket not publicly accessible"
  }
  assert {
    condition     = strcontains(base64decode(aws_launch_template.app.user_data), "/var/www/html/health") && strcontains(base64decode(aws_launch_template.app.user_data), "systemctl enable --now httpd")
    error_message = "R08 template boots a web server that serves /health"
  }
  assert {
    condition     = aws_autoscaling_group.app.min_size == 2 && aws_autoscaling_group.app.max_size == 6 && toset(aws_autoscaling_group.app.vpc_zone_identifier) == toset(aws_subnet.app[*].id) && contains(tolist(aws_autoscaling_group.app.target_group_arns), aws_lb_target_group.app.arn) && aws_autoscaling_group.app.launch_template[0].id == aws_launch_template.app.id && aws_autoscaling_policy.cpu.target_tracking_configuration[0].target_value == 60 && aws_autoscaling_policy.cpu.target_tracking_configuration[0].predefined_metric_specification[0].predefined_metric_type == "ASGAverageCPUUtilization"
    error_message = "R09 elastic pool 2-6 across app subnets, CPU target 60"
  }
  assert {
    condition     = aws_lb.web.load_balancer_type == "application" && !aws_lb.web.internal && toset(aws_lb.web.subnets) == toset(aws_subnet.public[*].id) && aws_lb_listener.http.port == 80 && aws_lb_listener.http.default_action[0].target_group_arn == aws_lb_target_group.app.arn && aws_lb_target_group.app.health_check[0].path == "/health" && aws_lb_target_group.app.health_check[0].matcher == "200"
    error_message = "R10 internet-facing L7 LB on :80 with /health probe"
  }
  assert {
    condition     = aws_db_instance.db.engine == "mysql" && aws_db_instance.db.engine_version == "8.0" && aws_db_instance.db.multi_az && !aws_db_instance.db.publicly_accessible && aws_db_instance.db.backup_retention_period == 7 && toset(aws_db_subnet_group.db.subnet_ids) == toset(aws_subnet.db[*].id)
    error_message = "R11 private, highly available MySQL 8.0 with 7-day backups"
  }
  assert {
    condition     = one([for o in aws_cloudfront_distribution.cdn.origin : o.domain_name]) == aws_lb.web.dns_name
    error_message = "R12 CDN fronts the load balancer"
  }
  assert {
    condition     = aws_cloudwatch_metric_alarm.cpu_high.metric_name == "CPUUtilization" && aws_cloudwatch_metric_alarm.cpu_high.threshold == 80 && aws_cloudwatch_metric_alarm.cpu_high.dimensions["AutoScalingGroupName"] == aws_autoscaling_group.app.name
    error_message = "R13 CPU alarm (>80) scoped to the pool"
  }
}
