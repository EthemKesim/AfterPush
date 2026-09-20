resource "aws_security_group" "alb" {
  name        = "launchforge-alb-sg"
  description = "Security group for LaunchForge ALB"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name    = "${var.project_name}-alb-sg"
    Project = var.project_name
  }
}

resource "aws_security_group" "ecs" {
  name        = "launchforge-ecs-sg"
  description = "Security group for LaunchForge ECS tasks"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name    = "${var.project_name}-ecs-sg"
    Project = var.project_name
  }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id

  cidr_ipv4   = "0.0.0.0/0"
  from_port   = 80
  to_port     = 80
  ip_protocol = "tcp"

  description = "Allow HTTP traffic from the internet"
}

resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  security_group_id = aws_security_group.ecs.id

  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 3000
  to_port                      = 3000
  ip_protocol                  = "tcp"

  description = "Allow application traffic only from the ALB"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_ecs" {
  security_group_id = aws_security_group.alb.id

  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 3000
  to_port                      = 3000
  ip_protocol                  = "tcp"

  description = "Allow ALB traffic to ECS tasks on port 3000"
}


# ---------------------------------------------------------
# ECS OUTBOUND SECURITY
# ---------------------------------------------------------

# AWS already maintains a list of the IP ranges used by S3
# in the selected region.
#
# This is a Terraform data source:
# it DOES NOT create a new prefix list.
# It reads the existing AWS-managed S3 prefix list.
data "aws_prefix_list" "s3" {
  name = "com.amazonaws.${var.aws_region}.s3"
}


# Allow ECS tasks to connect to our Interface VPC Endpoints.
#
# These endpoints currently provide private connectivity to:
# - ECR API
# - ECR Docker Registry
# - CloudWatch Logs
#
# HTTPS uses TCP port 443.
resource "aws_vpc_security_group_egress_rule" "ecs_to_vpc_endpoints" {
  security_group_id = aws_security_group.ecs.id

  referenced_security_group_id = aws_security_group.vpc_endpoints.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"

  description = "Allow HTTPS traffic from ECS tasks to VPC interface endpoints"
}


# S3 is different from our Interface Endpoints.
#
# We use an S3 Gateway VPC Endpoint, which does not have
# its own Security Group.
#
# Therefore, ECS is allowed to reach the AWS-managed
# S3 prefix list over HTTPS instead.
resource "aws_vpc_security_group_egress_rule" "ecs_to_s3" {
  security_group_id = aws_security_group.ecs.id

  prefix_list_id = data.aws_prefix_list.s3.id
  from_port      = 443
  to_port        = 443
  ip_protocol    = "tcp"

  description = "Allow HTTPS traffic from ECS tasks to S3"
}


# ---------------------------------------------------------
# VPC INTERFACE ENDPOINT SECURITY GROUP
# ---------------------------------------------------------

resource "aws_security_group" "vpc_endpoints" {
  name        = "launchforge-vpc-endpoints-sg"
  description = "Security group for VPC interface endpoints"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name    = "${var.project_name}-vpc-endpoints-sg"
    Project = var.project_name
  }
}


# Interface Endpoints accept HTTPS connections only
# when those connections originate from ECS tasks.
resource "aws_vpc_security_group_ingress_rule" "vpc_endpoints_from_ecs" {
  security_group_id = aws_security_group.vpc_endpoints.id

  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"

  description = "Allow HTTPS traffic from ECS tasks"
}