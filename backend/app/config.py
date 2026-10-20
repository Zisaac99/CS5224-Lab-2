from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_region: str = "ap-southeast-1"
    bucket: str = ""
    # Transient single-node EMR on EC2 cluster (fits the 5 vCPU EC2 quota)
    emr_release: str = "emr-7.14.0"
    emr_instance_type: str = "m5.xlarge"
    emr_service_role: str = "EMR_DefaultRole"
    emr_instance_profile: str = "EMR_EC2_DefaultRole"
    cluster_name_prefix: str = "lab2-follow-counts-"

    input_key: str = "input/twitter_combined.txt"
    script_key: str = "scripts/follow_counts.py"
    output_prefix: str = "output/"
    logs_prefix: str = "logs/"

    # Local copies uploaded to S3 if the objects are missing
    local_dataset: str = "../twitter_combined.txt"
    local_script: str = "../analysis/follow_counts.py"

    cors_origins: str = "*"


settings = Settings()
