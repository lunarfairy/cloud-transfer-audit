
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "6.71.0" }
  }
}
provider "aws" {
  region = var.region
}
variable "region" {
  type    = string
  default = "ap-southeast-2"
}
variable "db_password" {
  type      = string
  sensitive = true
}
locals {
  startup = "#!/bin/bash\ndnf install -y httpd php\nmkdir -p /var/www/html && echo ok > /var/www/html/health\nsystemctl enable --now httpd\n"
}

# K01 virtual network
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "ra-vpc" }
}

# K02 subnets: public, app and db tiers in two failure domains
data "aws_availability_zones" "az" {
  state = "available"
}
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet("10.0.0.0/16", 8, count.index)
  availability_zone       = data.aws_availability_zones.az.names[count.index]
  map_public_ip_on_launch = true
}
resource "aws_subnet" "app" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet("10.0.0.0/16", 8, 10 + count.index)
  availability_zone = data.aws_availability_zones.az.names[count.index]
}
resource "aws_subnet" "db" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet("10.0.0.0/16", 8, 20 + count.index)
  availability_zone = data.aws_availability_zones.az.names[count.index]
}

# K03 internet ingress/egress routing for the public tier
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
}
resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# K04 outbound-only NAT for the private app tier
resource "aws_eip" "nat" {
  domain = "vpc"
}
resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
}
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
}
resource "aws_route" "private_nat" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat.id
}
resource "aws_route_table_association" "app" {
  count          = 2
  subnet_id      = aws_subnet.app[count.index].id
  route_table_id = aws_route_table.private.id
}

# K05 traffic filtering between tiers
resource "aws_security_group" "lb" {
  name        = "ra-lb"
  description = "load balancer"
  vpc_id      = aws_vpc.main.id
}
resource "aws_security_group" "app" {
  name        = "ra-app"
  description = "application tier"
  vpc_id      = aws_vpc.main.id
}
resource "aws_security_group" "db" {
  name        = "ra-db"
  description = "database tier"
  vpc_id      = aws_vpc.main.id
}
resource "aws_vpc_security_group_ingress_rule" "lb_http" {
  security_group_id = aws_security_group.lb.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}
resource "aws_vpc_security_group_egress_rule" "lb_to_app" {
  security_group_id            = aws_security_group.lb.id
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}
resource "aws_vpc_security_group_ingress_rule" "app_from_lb" {
  security_group_id            = aws_security_group.app.id
  referenced_security_group_id = aws_security_group.lb.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}
resource "aws_vpc_security_group_egress_rule" "app_out" {
  security_group_id = aws_security_group.app.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
resource "aws_vpc_security_group_ingress_rule" "db_from_app" {
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = aws_security_group.app.id
  ip_protocol                  = "tcp"
  from_port                    = 3306
  to_port                      = 3306
}

# K06 workload identity with least-privilege access to the bucket
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}
resource "aws_iam_role" "app" {
  name               = "ra-app-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}
data "aws_iam_policy_document" "bucket_rw" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.media.arn}/*"]
  }
}
resource "aws_iam_role_policy" "bucket_rw" {
  name   = "ra-bucket-rw"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.bucket_rw.json
}
resource "aws_iam_instance_profile" "app" {
  name = "ra-app-profile"
  role = aws_iam_role.app.name
}

# K07 private object storage
resource "aws_s3_bucket" "media" {
  bucket_prefix = "ra-media-"
}
resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# K08 compute template
data "aws_ami" "linux" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}
resource "aws_launch_template" "app" {
  name_prefix            = "ra-app-"
  image_id               = data.aws_ami.linux.id
  instance_type          = "t3.micro"
  user_data              = base64encode(local.startup)
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile {
    name = aws_iam_instance_profile.app.name
  }
}

# K09 elastic compute pool with a metric-driven scaling policy
resource "aws_autoscaling_group" "app" {
  name                      = "ra-app-asg"
  min_size                  = 2
  max_size                  = 6
  desired_capacity          = 2
  vpc_zone_identifier       = aws_subnet.app[*].id
  target_group_arns         = [aws_lb_target_group.app.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 120
  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }
}
resource "aws_autoscaling_policy" "cpu" {
  name                   = "ra-cpu-target"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"
  target_tracking_configuration {
    target_value = 60
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
  }
}

# K10 layer-7 load balancer
resource "aws_lb" "web" {
  name               = "ra-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.lb.id]
}
resource "aws_lb_target_group" "app" {
  name     = "ra-app-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id
  health_check {
    path    = "/health"
    matcher = "200"
  }
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.web.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# K11 managed relational database
resource "aws_db_subnet_group" "db" {
  name       = "ra-db-subnets"
  subnet_ids = aws_subnet.db[*].id
}
resource "aws_db_instance" "db" {
  identifier              = "ra-mysql"
  engine                  = "mysql"
  engine_version          = "8.0"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  username                = "appadmin"
  password                = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.db.name
  vpc_security_group_ids  = [aws_security_group.db.id]
  backup_retention_period = 7
  multi_az                = true
  publicly_accessible     = false
  skip_final_snapshot     = true
}

# K12 content delivery network in front of the load balancer
data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}
resource "aws_cloudfront_distribution" "cdn" {
  enabled = true
  origin {
    domain_name = aws_lb.web.dns_name
    origin_id   = "alb"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }
  default_cache_behavior {
    target_origin_id       = "alb"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# K13 metric alarm on the compute pool
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "ra-cpu-high"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.app.name
  }
}
