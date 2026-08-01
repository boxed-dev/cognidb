"""Secrets management for sensitive configuration."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..core.exceptions import ConfigurationError

# OWASP 2024 guidance for PBKDF2-HMAC-SHA256 (>= 600_000 iterations).
KDF_ITERATIONS = 600_000
# Per-install random salt length in bytes.
SALT_BYTES = 16


class SecretsManager:
    """
    Secure secrets management.
    
    Supports:
    - Environment variables
    - Encrypted file storage
    - AWS Secrets Manager
    - HashiCorp Vault
    - Azure Key Vault
    """
    
    def __init__(self, provider: str = "env", **kwargs):
        """
        Initialize secrets manager.
        
        Args:
            provider: One of 'env', 'file', 'aws', 'vault', 'azure'
            **kwargs: Provider-specific configuration
        """
        self.provider = provider
        self.config = kwargs
        self._cache: dict[str, Any] = {}
        self._cipher: Fernet | None = None
        
        if provider == "file":
            self._init_file_provider()
        elif provider == "aws":
            self._init_aws_provider()
        elif provider == "vault":
            self._init_vault_provider()
        elif provider == "azure":
            self._init_azure_provider()
    
    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a secret value.
        
        Args:
            key: Secret key
            default: Default value if not found
            
        Returns:
            Secret value
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]
        
        value = None
        
        if self.provider == "env":
            value = os.getenv(key, default)
        elif self.provider == "file":
            value = self._get_file_secret(key, default)
        elif self.provider == "aws":
            value = self._get_aws_secret(key, default)
        elif self.provider == "vault":
            value = self._get_vault_secret(key, default)
        elif self.provider == "azure":
            value = self._get_azure_secret(key, default)
        
        # Cache the value
        if value is not None:
            self._cache[key] = value
        
        return value
    
    def set_secret(self, key: str, value: Any) -> None:
        """
        Store a secret value.
        
        Args:
            key: Secret key
            value: Secret value
        """
        if self.provider == "env":
            os.environ[key] = str(value)
        elif self.provider == "file":
            self._set_file_secret(key, value)
        elif self.provider == "aws":
            self._set_aws_secret(key, value)
        elif self.provider == "vault":
            self._set_vault_secret(key, value)
        elif self.provider == "azure":
            self._set_azure_secret(key, value)
        
        # Update cache
        self._cache[key] = value
    
    def delete_secret(self, key: str) -> None:
        """Delete a secret."""
        if self.provider == "env":
            os.environ.pop(key, None)
        elif self.provider == "file":
            self._delete_file_secret(key)
        elif self.provider == "aws":
            self._delete_aws_secret(key)
        elif self.provider == "vault":
            self._delete_vault_secret(key)
        elif self.provider == "azure":
            self._delete_azure_secret(key)
        
        # Remove from cache
        self._cache.pop(key, None)
    
    def clear_cache(self) -> None:
        """Clear the secrets cache."""
        self._cache.clear()
    
    # File-based provider methods
    
    def _init_file_provider(self) -> None:
        """Initialize file-based secrets provider."""
        secrets_file = self.config.get('secrets_file', 
                                     str(Path.home() / '.cognidb' / 'secrets.enc'))
        master_password = self.config.get('master_password')
        
        if not master_password:
            master_password = os.getenv('COGNIDB_MASTER_PASSWORD')
            if not master_password:
                raise ConfigurationError(
                    "Master password required for file-based secrets"
                )
        
        # Create directory if needed
        Path(secrets_file).parent.mkdir(parents=True, exist_ok=True)

        self.secrets_file = secrets_file
        # Derives the cipher from a per-install random salt and loads any
        # existing ciphertext. The salt is persisted beside the ciphertext so
        # decryption works across process restarts.
        self._load_secrets_file(master_password)

    @staticmethod
    def _derive_cipher(master_password: str, salt: bytes) -> Fernet:
        """Derive a Fernet cipher from the master password and a random salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=KDF_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        return Fernet(key)

    def _load_secrets_file(self, master_password: str) -> None:
        """Load secrets from the encrypted keystore (a salt+ciphertext envelope)."""
        path = Path(self.secrets_file)
        if not path.exists():
            # Fresh install: mint a new per-install salt; nothing to decrypt yet.
            self._salt = os.urandom(SALT_BYTES)
            self._cipher = self._derive_cipher(master_password, self._salt)
            self._secrets_data = {}
            return

        try:
            with open(path) as f:
                envelope = json.load(f)
            self._salt = bytes.fromhex(envelope['salt'])
            self._cipher = self._derive_cipher(master_password, self._salt)
            ciphertext = base64.b64decode(envelope['ciphertext'])
            decrypted_data = self._cipher.decrypt(ciphertext)
            self._secrets_data = json.loads(decrypted_data.decode())
        except Exception as e:
            raise ConfigurationError(f"Failed to load secrets file: {e}") from e

    def _save_secrets_file(self) -> None:
        """Save secrets to the encrypted keystore with 0600 permissions."""
        try:
            data = json.dumps(self._secrets_data).encode()
            ciphertext = self._cipher.encrypt(data)
            envelope = {
                'salt': self._salt.hex(),
                'ciphertext': base64.b64encode(ciphertext).decode('ascii'),
            }

            path = Path(self.secrets_file)
            with open(path, 'w') as f:
                json.dump(envelope, f)
            os.chmod(path, 0o600)
        except Exception as e:
            raise ConfigurationError(f"Failed to save secrets file: {e}") from e
    
    def _get_file_secret(self, key: str, default: Any) -> Any:
        """Get secret from file."""
        return self._secrets_data.get(key, default)
    
    def _set_file_secret(self, key: str, value: Any) -> None:
        """Set secret in file."""
        self._secrets_data[key] = value
        self._save_secrets_file()
    
    def _delete_file_secret(self, key: str) -> None:
        """Delete secret from file."""
        self._secrets_data.pop(key, None)
        self._save_secrets_file()
    
    # AWS Secrets Manager provider methods
    
    def _init_aws_provider(self) -> None:
        """Initialize AWS Secrets Manager provider."""
        try:
            import boto3
            self._aws_client = boto3.client(
                'secretsmanager',
                region_name=self.config.get('region', 'us-east-1')
            )
        except ImportError:
            raise ConfigurationError(
                "boto3 required for AWS Secrets Manager. Install with: pip install boto3"
            ) from None
    
    def _get_aws_secret(self, key: str, default: Any) -> Any:
        """Get secret from AWS Secrets Manager."""
        try:
            response = self._aws_client.get_secret_value(SecretId=key)
            if 'SecretString' in response:
                secret = response['SecretString']
                try:
                    return json.loads(secret)
                except json.JSONDecodeError:
                    return secret
            else:
                return base64.b64decode(response['SecretBinary'])
        except self._aws_client.exceptions.ResourceNotFoundException:
            return default
        except Exception as e:
            raise ConfigurationError(f"Failed to get AWS secret: {e}") from e
    
    def _set_aws_secret(self, key: str, value: Any) -> None:
        """Set secret in AWS Secrets Manager."""
        try:
            secret_string = json.dumps(value) if not isinstance(value, str) else value
            try:
                self._aws_client.update_secret(
                    SecretId=key,
                    SecretString=secret_string
                )
            except self._aws_client.exceptions.ResourceNotFoundException:
                self._aws_client.create_secret(
                    Name=key,
                    SecretString=secret_string
                )
        except Exception as e:
            raise ConfigurationError(f"Failed to set AWS secret: {e}") from e
    
    def _delete_aws_secret(self, key: str) -> None:
        """Delete secret from AWS Secrets Manager."""
        try:
            self._aws_client.delete_secret(
                SecretId=key,
                ForceDeleteWithoutRecovery=True
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to delete AWS secret: {e}") from e
    
    # HashiCorp Vault provider methods
    
    def _init_vault_provider(self) -> None:
        """Initialize HashiCorp Vault provider."""
        try:
            import hvac
            self._vault_client = hvac.Client(
                url=self.config.get('url', 'http://localhost:8200'),
                token=self.config.get('token') or os.getenv('VAULT_TOKEN')
            )
            if not self._vault_client.is_authenticated():
                raise ConfigurationError("Vault authentication failed")
        except ImportError:
            raise ConfigurationError(
                "hvac required for HashiCorp Vault. Install with: pip install hvac"
            ) from None
    
    def _get_vault_secret(self, key: str, default: Any) -> Any:
        """Get secret from HashiCorp Vault."""
        try:
            mount_point = self.config.get('mount_point', 'secret')
            response = self._vault_client.secrets.kv.v2.read_secret_version(
                path=key,
                mount_point=mount_point
            )
            return response['data']['data']
        except Exception:
            return default
    
    def _set_vault_secret(self, key: str, value: Any) -> None:
        """Set secret in HashiCorp Vault."""
        try:
            mount_point = self.config.get('mount_point', 'secret')
            self._vault_client.secrets.kv.v2.create_or_update_secret(
                path=key,
                secret=dict(value=value) if not isinstance(value, dict) else value,
                mount_point=mount_point
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to set Vault secret: {e}") from e
    
    def _delete_vault_secret(self, key: str) -> None:
        """Delete secret from HashiCorp Vault."""
        try:
            mount_point = self.config.get('mount_point', 'secret')
            self._vault_client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=key,
                mount_point=mount_point
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to delete Vault secret: {e}") from e
    
    # Azure Key Vault provider methods
    
    def _init_azure_provider(self) -> None:
        """Initialize Azure Key Vault provider."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            
            vault_url = self.config.get('vault_url')
            if not vault_url:
                raise ConfigurationError("vault_url required for Azure Key Vault")
            
            credential = DefaultAzureCredential()
            self._azure_client = SecretClient(
                vault_url=vault_url,
                credential=credential
            )
        except ImportError:
            raise ConfigurationError(
                "azure-keyvault-secrets required. Install with: "
                "pip install azure-keyvault-secrets azure-identity"
            ) from None
    
    def _get_azure_secret(self, key: str, default: Any) -> Any:
        """Get secret from Azure Key Vault."""
        try:
            secret = self._azure_client.get_secret(key)
            return secret.value
        except Exception:
            return default
    
    def _set_azure_secret(self, key: str, value: Any) -> None:
        """Set secret in Azure Key Vault."""
        try:
            value_str = json.dumps(value) if not isinstance(value, str) else value
            self._azure_client.set_secret(key, value_str)
        except Exception as e:
            raise ConfigurationError(f"Failed to set Azure secret: {e}") from e
    
    def _delete_azure_secret(self, key: str) -> None:
        """Delete secret from Azure Key Vault."""
        try:
            poller = self._azure_client.begin_delete_secret(key)
            poller.wait()
        except Exception as e:
            raise ConfigurationError(f"Failed to delete Azure secret: {e}") from e