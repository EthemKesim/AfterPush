variable "aws_region" {
  description = "AWS region for AfterPush infrastructure"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "afterpush"
}

variable "vpc_cidr" {
  description = "CIDR block for the AfterPush VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnets" {
  description = "Subnet configuration for AfterPush"

  type = map(object({
    cidr_block        = string
    availability_zone = string
    public            = bool
  }))

  default = {
    public-a = {
      cidr_block        = "10.0.1.0/24"
      availability_zone = "eu-central-1a"
      public            = true
    }

    public-b = {
      cidr_block        = "10.0.2.0/24"
      availability_zone = "eu-central-1b"
      public            = true
    }

    private-a = {
      cidr_block        = "10.0.11.0/24"
      availability_zone = "eu-central-1a"
      public            = false
    }

    private-b = {
      cidr_block        = "10.0.12.0/24"
      availability_zone = "eu-central-1b"
      public            = false
    }
  }
}

variable "alert_email" {
  description = "Email address that receives AfterPush CloudWatch alerts"
  type        = string
  sensitive   = true
}

variable "alb_access_mode" {
  description = "Exposure mode for the legacy ECS ALB. Public access requires an ACM certificate and explicit CIDR allowlist."
  type        = string
  default     = "internal"

  validation {
    condition     = contains(["internal", "public"], var.alb_access_mode)
    error_message = "alb_access_mode must be either internal or public."
  }
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN required for the legacy ECS ALB HTTPS listener."
  type        = string
  sensitive   = true
}

variable "public_alb_ingress_cidrs" {
  description = "Explicit IPv4 CIDRs permitted to reach a public legacy ECS ALB. Ignored while alb_access_mode is internal."
  type        = set(string)
  default     = []
}
