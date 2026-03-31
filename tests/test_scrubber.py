"""Tests for the PII scrubber."""

import json
from pathlib import Path

import pytest

from kajiba.schema import validate_record
from kajiba.scrubber import (
    PLACEHOLDER_CERT,
    PLACEHOLDER_CONNSTR,
    PLACEHOLDER_EMAIL,
    PLACEHOLDER_HOSTNAME,
    PLACEHOLDER_HEX_TOKEN,
    PLACEHOLDER_IP,
    PLACEHOLDER_KEY,
    PLACEHOLDER_PATH,
    PLACEHOLDER_PHONE,
    FlaggedItem,
    flag_org_domains,
    scrub_record,
    scrub_text,
)
from kajiba.scrubber_llm import scrub_semantic

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Individual pattern category tests
# ---------------------------------------------------------------------------


class TestFilePathScrubbing:
    """Test file path pattern detection."""

    def test_linux_home_dir(self) -> None:
        result = scrub_text("Check /home/username/projects/app/main.py")
        assert PLACEHOLDER_PATH in result.scrubbed_text
        assert "username" not in result.scrubbed_text
        assert result.stats.get("file_paths", 0) > 0

    def test_macos_home_dir(self) -> None:
        result = scrub_text("File at /Users/johndoe/Documents/report.pdf")
        assert PLACEHOLDER_PATH in result.scrubbed_text
        assert "johndoe" not in result.scrubbed_text

    def test_windows_path(self) -> None:
        result = scrub_text("Located at C:\\Users\\jsmith\\AppData\\config.json")
        assert PLACEHOLDER_PATH in result.scrubbed_text
        assert "jsmith" not in result.scrubbed_text

    def test_tilde_path(self) -> None:
        result = scrub_text("Config is at ~/.ssh/config")
        assert PLACEHOLDER_PATH in result.scrubbed_text


class TestApiKeyScrubbing:
    """Test API key pattern detection."""

    def test_openai_key(self) -> None:
        result = scrub_text("Use key sk-abcdefghijklmnopqrstuvwxyz1234567890")
        assert PLACEHOLDER_KEY in result.scrubbed_text
        assert "sk-" not in result.scrubbed_text

    def test_github_pat(self) -> None:
        result = scrub_text("Token: ghp_abcdefghijklmnopqrstuvwxyz1234567890")
        assert PLACEHOLDER_KEY in result.scrubbed_text

    def test_gitlab_pat(self) -> None:
        result = scrub_text("Token: glpat-xxxxxxxxxxxxxxxxxxxx")
        assert PLACEHOLDER_KEY in result.scrubbed_text

    def test_aws_access_key(self) -> None:
        result = scrub_text("AWS key: AKIAIOSFODNN7EXAMPLE")
        assert PLACEHOLDER_KEY in result.scrubbed_text

    def test_jwt_token(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = scrub_text(f"Auth: {jwt}")
        assert PLACEHOLDER_KEY in result.scrubbed_text

    def test_bearer_token(self) -> None:
        result = scrub_text("Authorization: Bearer mytoken123.secret")
        assert PLACEHOLDER_KEY in result.scrubbed_text

    def test_token_assignment(self) -> None:
        result = scrub_text('token = "my-secret-value"')
        assert PLACEHOLDER_KEY in result.scrubbed_text


class TestNetworkScrubbing:
    """Test network pattern detection."""

    def test_ipv4_address(self) -> None:
        result = scrub_text("Connect to 192.168.1.100 on port 8080")
        assert PLACEHOLDER_IP in result.scrubbed_text
        assert "192.168.1.100" not in result.scrubbed_text

    def test_internal_hostname(self) -> None:
        result = scrub_text("Server at db.internal is down")
        assert PLACEHOLDER_HOSTNAME in result.scrubbed_text


class TestEmailScrubbing:
    """Test email pattern detection."""

    def test_email_address(self) -> None:
        result = scrub_text("Contact john.smith@acmecorp.com for help")
        assert PLACEHOLDER_EMAIL in result.scrubbed_text
        assert "john.smith" not in result.scrubbed_text

    def test_email_with_plus(self) -> None:
        result = scrub_text("Send to user+tag@example.com")
        assert PLACEHOLDER_EMAIL in result.scrubbed_text


class TestPhoneScrubbing:
    """Test phone number pattern detection."""

    def test_us_phone(self) -> None:
        result = scrub_text("Call +1 (555) 123-4567")
        assert PLACEHOLDER_PHONE in result.scrubbed_text

    def test_phone_with_dots(self) -> None:
        result = scrub_text("Phone: 555.123.4567")
        assert PLACEHOLDER_PHONE in result.scrubbed_text


class TestCryptoScrubbing:
    """Test SSH key and certificate detection."""

    def test_pem_certificate(self) -> None:
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAK\n-----END RSA PRIVATE KEY-----"
        result = scrub_text(f"Key: {pem}")
        assert PLACEHOLDER_CERT in result.scrubbed_text
        assert "MIIEpAIBAAK" not in result.scrubbed_text

    def test_ssh_key(self) -> None:
        result = scrub_text("ssh-rsa AAAA1234567890abcdefghijklmnopqrstuvwxyz user@host")
        assert PLACEHOLDER_CERT in result.scrubbed_text


class TestConnectionStringScrubbing:
    """Test connection string detection."""

    def test_postgres_url(self) -> None:
        result = scrub_text("postgres://admin:pass@db.host:5432/mydb")
        assert PLACEHOLDER_CONNSTR in result.scrubbed_text
        assert "admin:pass" not in result.scrubbed_text

    def test_mysql_url(self) -> None:
        result = scrub_text("mysql://root:password@localhost:3306/appdb")
        assert PLACEHOLDER_CONNSTR in result.scrubbed_text

    def test_mongodb_url(self) -> None:
        result = scrub_text("mongodb://user:pass@mongo.host:27017/db")
        assert PLACEHOLDER_CONNSTR in result.scrubbed_text

    def test_redis_url(self) -> None:
        result = scrub_text("redis://cache.internal:6379/0")
        assert PLACEHOLDER_CONNSTR in result.scrubbed_text

    def test_odbc_connection(self) -> None:
        result = scrub_text("Server=db-prod.corp;Database=maindb;")
        assert PLACEHOLDER_CONNSTR in result.scrubbed_text


# ---------------------------------------------------------------------------
# False positive tests — things that should NOT be redacted
# ---------------------------------------------------------------------------


class TestFalsePositives:
    """Test that the scrubber doesn't over-redact."""

    def test_tool_names_preserved(self) -> None:
        """Tool names like 'terminal' should not be redacted."""
        result = scrub_text("The terminal tool ran docker build successfully.")
        assert "terminal" in result.scrubbed_text
        assert "docker" in result.scrubbed_text

    def test_normal_urls_not_path_redacted(self) -> None:
        """Normal URLs should not be matched as file paths."""
        result = scrub_text("Visit https://docs.python.org for documentation")
        # The URL shouldn't be matched as a file path
        assert "docs.python.org" in result.scrubbed_text

    def test_short_strings_not_api_keys(self) -> None:
        """Short strings should not be matched as API keys."""
        result = scrub_text("The variable 'count' has value 42")
        assert "count" in result.scrubbed_text
        assert "42" in result.scrubbed_text

    def test_plain_text_preserved(self) -> None:
        """Normal conversational text should be completely preserved."""
        text = "I need help writing a Python function to sort a list."
        result = scrub_text(text)
        assert result.scrubbed_text == text
        assert len(result.redactions) == 0


# ---------------------------------------------------------------------------
# Full record scrubbing tests
# ---------------------------------------------------------------------------


class TestRecordScrubbing:
    """Test full record scrubbing."""

    def test_pii_record_scrub(self) -> None:
        """The PII fixture should have many redactions."""
        data = _load_fixture("pii_trajectory.json")
        record = validate_record(data)
        scrubbed, scrub_log = scrub_record(record)

        # Should have scrubbed file paths
        assert scrub_log.file_paths_redacted > 0
        # Should have scrubbed API keys
        assert scrub_log.api_keys_redacted > 0
        # Should have scrubbed emails
        assert scrub_log.emails_redacted > 0
        # Should have scrubbed connection strings
        assert scrub_log.connection_strings_redacted > 0

    def test_scrub_preserves_structure(self) -> None:
        """Scrubbing should not change the record structure."""
        data = _load_fixture("pii_trajectory.json")
        record = validate_record(data)
        scrubbed, _ = scrub_record(record)

        assert scrubbed.schema_version == record.schema_version
        assert scrubbed.record_type == record.record_type
        assert len(scrubbed.trajectory.conversations) == len(record.trajectory.conversations)
        assert scrubbed.trajectory.turn_count == record.trajectory.turn_count

    def test_nested_tool_outputs_scrubbed(self) -> None:
        """Tool call outputs should also be scrubbed."""
        data = _load_fixture("pii_trajectory.json")
        record = validate_record(data)
        scrubbed, _ = scrub_record(record)

        # The first gpt turn has a tool call output with secrets
        first_gpt = scrubbed.trajectory.conversations[1]
        assert first_gpt.tool_calls is not None
        tool_output = first_gpt.tool_calls[0].tool_output
        # Connection string should be redacted
        assert "supersecretpassword" not in tool_output

    def test_clean_record_unchanged(self) -> None:
        """A clean record should have zero redactions."""
        data = _load_fixture("minimal_trajectory.json")
        record = validate_record(data)
        scrubbed, scrub_log = scrub_record(record)

        assert scrub_log.file_paths_redacted == 0
        assert scrub_log.api_keys_redacted == 0
        assert scrub_log.emails_redacted == 0

    def test_scrub_log_accuracy(self) -> None:
        """Scrub log counts should accurately reflect redactions."""
        data = _load_fixture("pii_trajectory.json")
        record = validate_record(data)
        _, scrub_log = scrub_record(record)

        # Verify counts are positive integers
        assert isinstance(scrub_log.file_paths_redacted, int)
        assert isinstance(scrub_log.api_keys_redacted, int)
        total = (
            scrub_log.file_paths_redacted
            + scrub_log.api_keys_redacted
            + scrub_log.emails_redacted
            + scrub_log.network_redacted
            + scrub_log.phone_redacted
            + scrub_log.crypto_redacted
            + scrub_log.connection_strings_redacted
        )
        assert total > 0

    def test_pain_point_descriptions_scrubbed(self) -> None:
        """Pain point descriptions containing PII should be scrubbed."""
        data = _load_fixture("pii_trajectory.json")
        record = validate_record(data)
        scrubbed, _ = scrub_record(record)

        assert scrubbed.pain_points is not None
        pp_desc = scrubbed.pain_points[0].description
        # The path with username should be scrubbed
        assert "johnsmith" not in pp_desc

    def test_user_comment_scrubbed(self) -> None:
        """Outcome user_comment containing PII should be scrubbed."""
        data = _load_fixture("pii_trajectory.json")
        record = validate_record(data)
        scrubbed, _ = scrub_record(record)

        assert scrubbed.outcome is not None
        comment = scrubbed.outcome.user_comment
        assert "john.smith@acmecorp.com" not in comment


# ---------------------------------------------------------------------------
# PRIV-06: IP false positive fix tests
# ---------------------------------------------------------------------------


class TestIPFalsePositiveFix:
    """Test that version strings are NOT redacted as IPs (PRIV-06)."""

    def test_python_version_preserved(self) -> None:
        result = scrub_text("Python 3.11.0.0")
        assert result.scrubbed_text == "Python 3.11.0.0"

    def test_cuda_version_preserved(self) -> None:
        result = scrub_text("CUDA 12.1.0.0")
        assert result.scrubbed_text == "CUDA 12.1.0.0"

    def test_node_version_preserved(self) -> None:
        result = scrub_text("Node v18.17.0.0")
        assert result.scrubbed_text == "Node v18.17.0.0"

    def test_pip_version_preserved(self) -> None:
        result = scrub_text("pip 23.1.2.0")
        assert result.scrubbed_text == "pip 23.1.2.0"

    def test_version_keyword_preserved(self) -> None:
        result = scrub_text("version 1.2.3.4")
        assert result.scrubbed_text == "version 1.2.3.4"

    def test_real_ip_still_redacted(self) -> None:
        result = scrub_text("Connect to 192.168.1.100 on port 8080")
        assert PLACEHOLDER_IP in result.scrubbed_text
        assert "192.168.1.100" not in result.scrubbed_text

    def test_private_ip_still_redacted(self) -> None:
        result = scrub_text("Server at 10.0.0.1")
        assert PLACEHOLDER_IP in result.scrubbed_text
        assert "10.0.0.1" not in result.scrubbed_text

    def test_bind_all_ip_still_redacted(self) -> None:
        result = scrub_text("Bind to 0.0.0.0")
        assert PLACEHOLDER_IP in result.scrubbed_text
        assert "0.0.0.0" not in result.scrubbed_text


# ---------------------------------------------------------------------------
# PRIV-04: Hex token scrubbing tests
# ---------------------------------------------------------------------------


class TestHexTokenScrubbing:
    """Test that hex tokens with context keywords are scrubbed (PRIV-04)."""

    def test_token_equals_hex(self) -> None:
        result = scrub_text("token=abc123def456abc123def456abc123def456abcd")
        assert "abc123def456" not in result.scrubbed_text

    def test_key_equals_hex(self) -> None:
        result = scrub_text("key=1234567890abcdef1234567890abcdef12345678")
        assert "1234567890abcdef" not in result.scrubbed_text

    def test_secret_quoted_hex(self) -> None:
        result = scrub_text("secret = 'aabbccddee1234567890aabbccddee1234567890'")
        assert "aabbccddee" not in result.scrubbed_text

    def test_api_key_colon_hex(self) -> None:
        result = scrub_text("api_key: ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00")
        assert "ff00ff00" not in result.scrubbed_text

    def test_commit_hash_preserved(self) -> None:
        """Git commit hashes without context keyword should NOT be scrubbed."""
        text = "commit abc123def456abc123def456abc123def456abcd"
        result = scrub_text(text)
        assert "abc123def456" in result.scrubbed_text

    def test_sha1_hash_preserved(self) -> None:
        """SHA1 references without context keyword should NOT be scrubbed."""
        text = "sha1 abc123def456abc123def456abc123def456abcd"
        result = scrub_text(text)
        assert "abc123def456" in result.scrubbed_text


# ---------------------------------------------------------------------------
# PRIV-05: Org domain flagging tests
# ---------------------------------------------------------------------------


class TestOrgDomainFlagging:
    """Test org domain flagging — flag for review, do NOT auto-redact (PRIV-05)."""

    def test_org_domain_not_auto_redacted(self) -> None:
        """Org domains should NOT be auto-redacted in scrub_text output."""
        result = scrub_text("Visit acme.io for info")
        assert "acme.io" in result.scrubbed_text

    def test_flag_org_domain_detected(self) -> None:
        flagged = flag_org_domains("Visit acme.io for info")
        assert len(flagged) == 1
        assert flagged[0].text == "acme.io"
        assert isinstance(flagged[0], FlaggedItem)

    def test_safe_domain_github_io(self) -> None:
        flagged = flag_org_domains("Check github.io")
        assert len(flagged) == 0

    def test_safe_domain_python_org(self) -> None:
        flagged = flag_org_domains("See python.org docs")
        assert len(flagged) == 0

    def test_company_tld_flagged(self) -> None:
        flagged = flag_org_domains("Contact us at mycorp.company")
        assert len(flagged) == 1
        assert flagged[0].text == "mycorp.company"

    def test_safe_domain_crates_io(self) -> None:
        flagged = flag_org_domains("File at crates.io/pkg")
        assert len(flagged) == 0


# ---------------------------------------------------------------------------
# ScrubResult.flagged and ScrubLog.items_flagged tests
# ---------------------------------------------------------------------------


class TestFlaggingSupport:
    """Test that ScrubResult has flagged field and ScrubLog has items_flagged."""

    def test_scrub_result_has_flagged(self) -> None:
        result = scrub_text("some text")
        assert hasattr(result, "flagged")
        assert isinstance(result.flagged, list)

    def test_scrub_log_items_flagged_default(self) -> None:
        from kajiba.schema import ScrubLog
        log = ScrubLog()
        assert log.items_flagged == 0

    def test_scrub_log_items_flagged_set(self) -> None:
        from kajiba.schema import ScrubLog
        log = ScrubLog(items_flagged=3)
        assert log.items_flagged == 3


# ---------------------------------------------------------------------------
# LLM scrubber stub test
# ---------------------------------------------------------------------------


class TestLLMScrubberStub:
    """Test that the LLM scrubber stub raises NotImplementedError."""

    def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            scrub_semantic("some text", model_fn=lambda x: x)
