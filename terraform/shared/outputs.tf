output "ecr_repository_url" {
  description = "ECR repository URL for the AfterPush API."
  value       = aws_ecr_repository.api.repository_url
}

output "runtime_worker_ecr_repository_url" {
  description = "ECR repository URL for the AfterPush runtime worker."
  value       = aws_ecr_repository.runtime_worker.repository_url
}

output "github_actions_ecr_role_arn" {
  description = "IAM role ARN used by GitHub Actions to push Docker images."
  value       = aws_iam_role.github_actions_ecr.arn
}
