output "cluster_name" {
  description = "Name of the EKS cluster."
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "API endpoint of the EKS cluster."
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_version" {
  description = "Kubernetes version running on the EKS cluster."
  value       = aws_eks_cluster.main.version
}

output "node_group_name" {
  description = "Name of the EKS managed node group."
  value       = aws_eks_node_group.main.node_group_name
}

output "vpc_id" {
  description = "VPC used by the EKS validation environment."
  value       = aws_vpc.eks.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs used by the EKS cluster and node group."
  value = [
    aws_subnet.public_a.id,
    aws_subnet.public_b.id,
  ]
}

output "ecr_repository_url" {
  description = "ECR repository URL for the AfterPush API."
  value       = aws_ecr_repository.api.repository_url
}