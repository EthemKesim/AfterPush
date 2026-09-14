output "vpc_id" {
  description = "ID of the AfterPush VPC"
  value       = aws_vpc.main.id
}

output "alb_dns_name" {
  description = "Public DNS name of the AfterPush Application Load Balancer"
  value       = aws_lb.main.dns_name
}