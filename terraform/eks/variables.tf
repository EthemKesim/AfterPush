variable "aws_region" {
  description = "AWS region used for the EKS validation environment."
  type        = string
  default     = "eu-central-1"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used by Terraform."
  type        = string
  default     = "terraform"
}

variable "cluster_name" {
  description = "Name of the AfterPush EKS cluster."
  type        = string
  default     = "afterpush-eks"
}

variable "kubernetes_version" {
  description = "Kubernetes version used by the EKS cluster. EKS 1.28+ provides default envelope encryption for Kubernetes API data."
  type        = string
  default     = "1.36"

  validation {
    condition     = can(regex("^1\\.(2[89]|[3-9][0-9])$", var.kubernetes_version))
    error_message = "The secure EKS profile requires Kubernetes 1.28 or later for default envelope encryption."
  }
}

variable "node_instance_types" {
  description = "EC2 instance types used by the EKS managed node group."
  type        = list(string)
  default     = ["c7i-flex.large"]
}

variable "node_desired_size" {
  description = "Desired number of worker nodes."
  type        = number
  default     = 1
}

variable "node_min_size" {
  description = "Minimum number of worker nodes."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of worker nodes."
  type        = number
  default     = 2
}
