import pytest
from database_mcp.privacy import privacy_engine, PrivacyEngine
from database_mcp.sql.executor import SQLExecutor
from unittest.mock import AsyncMock

def test_privacy_engine_text():
    """Test text tokenization and detokenization of sensitive PII (UID and phone)."""
    engine = PrivacyEngine()
    
    # Raw message
    raw_msg = "Please find the account details for UID 5912345, mobile 9876543210."
    
    # Tokenize
    tokenized = engine.tokenize_text(raw_msg)
    assert "<//UID-" in tokenized
    assert "<//PHONE-" in tokenized
    assert "5912345" not in tokenized
    assert "9876543210" not in tokenized
    
    # Detokenize
    detokenized = engine.detokenize_text(tokenized)
    assert detokenized == raw_msg

def test_privacy_engine_record():
    """Test record encryption and decryption of dictionary values."""
    engine = PrivacyEngine()
    
    raw_record = {
        "consumer_id": 12345,
        "consumer_no": "59102938475",
        "consumer_name": "Rohan Sen",
        "mobile_no": 9988776655,
        "address": "Bhubaneswar Feeder Circle",
        "latitude": 20.296,
        "longitude": 85.824,
        "gps_captured": "20.296,85.824",
        "feeder_id": 999 # Non-sensitive
    }
    
    # Encrypt record
    encrypted = engine.encrypt_record(raw_record)
    
    assert encrypted["feeder_id"] == 999
    assert "<//UID-" in encrypted["consumer_no"]
    assert "<//NAME-" in encrypted["consumer_name"]
    assert "<//PHONE-" in encrypted["mobile_no"]
    assert "<//ADDRESS-" in encrypted["address"]
    assert "<//LAT-" in encrypted["latitude"]
    assert "<//LON-" in encrypted["longitude"]
    assert "<//GPS-" in encrypted["gps_captured"]
    
    # Decrypt record
    decrypted = engine.decrypt_record(encrypted)
    assert decrypted["consumer_no"] == "59102938475"
    assert decrypted["consumer_name"] == "Rohan Sen"
    assert decrypted["mobile_no"] == "9988776655" # String representation is fine
    assert decrypted["address"] == "Bhubaneswar Feeder Circle"
    assert float(decrypted["latitude"]) == 20.296
    assert float(decrypted["longitude"]) == 85.824
    assert decrypted["gps_captured"] == "20.296,85.824"
    assert decrypted["feeder_id"] == 999

@pytest.mark.asyncio
async def test_sql_executor_privacy_flow(mock_cursor):
    """Test that SQLExecutor executes query directly and returns raw results."""
    real_phone = "9090909090"
    
    # 2. Setup mock database cursor response
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[
        ("John Doe", real_phone)
    ])
    mock_cursor.description = [("consumer_name",), ("mobile_no",)]
    
    from database_mcp.provider.connection import ConnectionProvider
    await ConnectionProvider.initialize()
    
    # Run SQL
    sql = f"SELECT consumer_name, mobile_no FROM consumer_master WHERE mobile_no = '{real_phone}'"
    res = await SQLExecutor.execute(sql)
    
    # Assertions
    assert res["success"] is True
    # The SQL executed on the database should have been passed directly
    mock_cursor.execute.assert_called_once_with(
        f"SELECT consumer_name, mobile_no FROM consumer_master WHERE mobile_no = '{real_phone}'",
        None
    )
    
    # The output rows should be raw (unencrypted)
    row = res["rows"][0]
    assert row[0] == "John Doe"
    assert row[1] == real_phone
