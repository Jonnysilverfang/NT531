provider "aws" {
  profile             = "nt533-lab"
  region              = "us-east-1"
  allowed_account_ids = ["620306387033"]

  default_tags {
    tags = {
      Project   = "NT531"
      ManagedBy = "Terraform"
      Purpose   = "Learning"
    }
  }
}

# Separate, non-overlapping private address ranges.
resource "aws_vpc" "a" {
  cidr_block           = "10.10.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "nt531-vpc-a" }
}

resource "aws_vpc" "b" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "nt531-vpc-b" }
}
