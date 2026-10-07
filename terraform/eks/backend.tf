terraform {
  backend "s3" {
    bucket       = "afterpush-terraform-state-833090513321"
    key          = "afterpush/eks-validation/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}