import os
import pytest
import aiohttp
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.patcher.downloader import Downloader, RangeRequest

class MockRequestContextManager:
    """
    Mimics aiohttp._RequestContextManager:
        • awaitable –  await obj  → MockResponse
        • async-CM  –  async with obj as resp:
    """
    def __init__(self, response):
        self._resp = response

    # await obj  →  self._resp
    def __await__(self):
        async def _coro():
            return self._resp
        return _coro().__await__()

    # async with obj as resp:
    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, exc_type, exc, tb):
        pass

@pytest.fixture
def mock_session():
    """Create a mock aiohttp session for testing."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    # Mock the connector to prevent real network requests
    session._connector = AsyncMock(spec=aiohttp.TCPConnector)
    session._connector.connect = AsyncMock()
    # Make async context manager methods return the session itself
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session

@pytest.fixture
def sample_bundle_index():
    """Create a sample bundle index for testing."""
    return {
        "bundle1": {
            "block1": {
                "hash": "block1",
                "blockOffset": 0,
                "length": 100
            },
            "block2": {
                "hash": "block2",
                "blockOffset": 100,
                "length": 200
            },
            "block3": {
                "hash": "block3",
                "blockOffset": 300,
                "length": 150
            }
        },
        "bundle2": {
            "block4": {
                "hash": "block4",
                "blockOffset": 0,
                "length": 150
            },
            "block5": {
                "hash": "block5",
                "blockOffset": 150,
                "length": 250
            }
        }
    }

@pytest.fixture
def downloader(tmp_path, sample_bundle_index):
    """Create a Downloader instance with mocked dependencies."""
    patch_data_path = "http://test.example.com"  # Use http:// to match isURL check
    
    # Mock getPatchData to return our sample bundle index
    with patch('src.util.getPatchData', return_value={"bundles": sample_bundle_index}):
        downloader = Downloader(patch_data_path, use_compression=False)
        # The bundle_index will be populated by Downloader.__init__ using the mocked getPatchData
        return downloader

@pytest.mark.asyncio
async def test_create_range_requests(downloader):
    """Test creation of range requests from bundle blocks."""
    bundle_id = "bundle1"
    needed_blocks = ["block1", "block3"]
    
    ranges = downloader._create_range_requests(bundle_id, needed_blocks)
    
    assert len(ranges) == 2
    assert ranges[0] == RangeRequest(0, 99, "block1")
    assert ranges[1] == RangeRequest(300, 449, "block3")
    assert ranges[0].start < ranges[1].start  # Verify sorting

@pytest.mark.asyncio
async def test_fetch_bundle_ranges_multipart(downloader, mock_session):
    """Test successful multipart range request handling."""
    bundle_id = "bundle1"
    ranges = [
        RangeRequest(0, 99, "block1"),
        RangeRequest(100, 299, "block2")
    ]
    local_blocks = {}
    
    # Create mock multipart response
    boundary = "test_boundary"
    mock_response = MockResponse(
        status=206,
        headers={"Content-Type": f'multipart/byteranges; boundary="{boundary}"'},
        body=(
            f"--{boundary}\r\n"
            "Content-Range: bytes 0-99/1000\r\n\r\n"
            "block1_data\r\n"
            f"--{boundary}\r\n"
            "Content-Range: bytes 100-299/1000\r\n\r\n"
            "block2_data\r\n"
            f"--{boundary}--\r\n"
        ).encode()
    )
    
    # Create a mock that returns our response and tracks calls
    mock_get = Mock(return_value=MockRequestContextManager(mock_response))
    mock_session.get = mock_get
    
    await downloader._fetch_bundle_ranges(mock_session, bundle_id, ranges, local_blocks)
    
    # Verify request was made with correct range header
    assert mock_get.call_count == 1
    call_kwargs = mock_get.call_args[1]
    assert "Range" in call_kwargs["headers"]
    assert call_kwargs["headers"]["Range"] == "bytes=0-99,bytes=100-299"
    
    # Verify blocks were processed correctly
    assert "block1" in local_blocks
    assert "block2" in local_blocks
    assert local_blocks["block1"] == b"block1_data"
    assert local_blocks["block2"] == b"block2_data"

@pytest.mark.asyncio
async def test_fetch_bundle_ranges_single_range(downloader, mock_session):
    """Test handling of single range response."""
    bundle_id = "bundle1"
    ranges = [RangeRequest(0, 99, "block1")]
    local_blocks = {}
    
    # Create mock single range response
    mock_response = MockResponse(
        status=206,
        headers={"Content-Type": "application/octet-stream"},
        body=b"block1_data"
    )
    
    # Create a mock that returns our response
    mock_get = Mock(return_value=MockRequestContextManager(mock_response))
    mock_session.get = mock_get
    
    await downloader._fetch_bundle_ranges(mock_session, bundle_id, ranges, local_blocks)
    
    assert "block1" in local_blocks
    assert local_blocks["block1"] == b"block1_data"

@pytest.mark.asyncio
async def test_fetch_bundle_ranges_fallback(downloader, mock_session):
    """Test fallback to full bundle download when range requests not supported."""
    bundle_id = "bundle1"
    ranges = [
        RangeRequest(0, 99, "block1"),
        RangeRequest(100, 299, "block2")
    ]
    local_blocks = {}
    
    # Create mock non-206 response
    mock_response = MockResponse(
        status=200,
        body=b"full_bundle_data"
    )
    
    # Create a mock that returns our response
    mock_get = Mock(return_value=MockRequestContextManager(mock_response))
    mock_session.get = mock_get
    
    with patch.object(downloader, '_process_bundle', new_callable=AsyncMock) as mock_process:
        await downloader._fetch_bundle_ranges(mock_session, bundle_id, ranges, local_blocks)
        mock_process.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_remote_integration(downloader, mock_session):
    """Test integration of range requests in the main fetch method."""
    bundles = {
        "bundle1": ["block1", "block2"],
        "bundle2": ["block4"]
    }
    blocks_to_download = {"block6"}
    local_blocks = {}
    
    # Create mock responses that support async context manager
    boundary = "test_boundary"
    bundle1_response = MockResponse(
        status=206,
        headers={"Content-Type": f'multipart/byteranges; boundary="{boundary}"'},
        body=(
            f"--{boundary}\r\n"
            "Content-Range: bytes 0-99/1000\r\n\r\n"
            "block1_data\r\n"
            f"--{boundary}\r\n"
            "Content-Range: bytes 100-299/1000\r\n\r\n"
            "block2_data\r\n"
            f"--{boundary}--\r\n"
        ).encode()
    )
    
    bundle2_response = MockResponse(
        status=206,
        headers={"Content-Type": "application/octet-stream"},
        body=b"block4_data"
    )
    
    block_response = MockResponse(
        status=200,
        body=b"block6_data"
    )
    
    # Create a mock that returns different responses based on URL
    def mock_get(url, **kwargs):
        if "bundle1" in str(url):
            return MockRequestContextManager(bundle1_response)
        elif "bundle2" in str(url):
            return MockRequestContextManager(bundle2_response)
        else:
            return MockRequestContextManager(block_response)
    
    # Set up the mock to use our function
    mock_session.get = Mock(side_effect=mock_get)
    
    # Mock both isURL and getPatchData to ensure remote fetch path
    with patch('src.util.isURL', return_value=True), \
         patch('src.util.getPatchData', return_value={"bundles": downloader.bundle_index}), \
         patch('aiohttp.ClientSession', return_value=mock_session):
        await downloader.fetch(bundles, blocks_to_download, local_blocks)
    
    # Verify all blocks were downloaded
    assert len(local_blocks) == 4
    assert local_blocks["block1"] == b"block1_data"
    assert local_blocks["block2"] == b"block2_data"
    assert local_blocks["block4"] == b"block4_data"
    assert local_blocks["block6"] == b"block6_data"

@pytest.mark.asyncio
async def test_process_multipart_response_invalid_format(downloader):
    """Test handling of invalid multipart response format."""
    body = b"Invalid multipart format"
    boundary = "test_boundary"
    ranges = [RangeRequest(0, 99, "block1")]
    local_blocks = {}
    
    await downloader._process_multipart_response(body, boundary, ranges, local_blocks)
    assert "block1" not in local_blocks  # Should not process invalid format

@pytest.mark.asyncio
async def test_process_multipart_response_missing_range(downloader):
    """Test handling of multipart response with missing range header."""
    boundary = "test_boundary"
    body = (
        f"--{boundary}\r\n"
        "Content-Type: application/octet-stream\r\n\r\n"
        "block1_data\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    ranges = [RangeRequest(0, 99, "block1")]
    local_blocks = {}
    
    await downloader._process_multipart_response(body, boundary, ranges, local_blocks)
    assert "block1" not in local_blocks  # Should not process without range header

class MockResponse:
    """A class that properly implements the async context manager protocol."""
    def __init__(self, status=200, headers=None, body=None):
        self.status = status
        self.headers = headers or {}
        self._body = body or b""
    
    async def read(self):
        return self._body
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
