# Spark-TTS Runpod Serverless API Documentation

## Base Endpoint

```
https://api.runpod.ai/v2/{your-endpoint-id}/runsync
```

## Authentication

Include your Runpod API key in the Authorization header:
```
Authorization: Bearer {your-runpod-api-key}
```

## Request Format

### HTTP Method
`POST`

### Headers
```
Content-Type: application/json
Authorization: Bearer {your-runpod-api-key}
```

### Request Body Structure

```json
{
  "input": {
    // Required parameters
    "text": "string",
    
    // Optional parameters
    "prompt_text": "string",
    "prompt_speech_url": "string",
    "output_name": "string",
    "speaker_gender": "string",
    "pitch_shift": "number",
    "speed_shift": "number",
    "multi_sentence_gap": "number",
    "task_token": "string",
    "temperature": "number",
    "top_p": "number",
    "max_length": "integer",
    "enable_whisperx": "boolean",
    "enable_subtitles": "boolean"
  }
}
```

## Parameter Details

### Required Parameters

#### `text` (string, required)
The text to be converted to speech. Supports multiple languages including English and Chinese.

**Example**: `"Hello, welcome to Spark-TTS!"`

### Optional Parameters

#### `prompt_text` (string)
The transcript of the reference audio for voice cloning. Should match the content of `prompt_speech_url`.

**Example**: `"This is how the reference speaker sounds."`

#### `prompt_speech_url` (string)
S3 URL or pre-signed URL to the reference audio file for voice cloning.

**Supported formats**: WAV, MP3, FLAC
**Example**: `"s3://my-bucket/voices/reference.wav"`

#### `output_name` (string)
Prefix for the output file name. The system will append a unique ID.

**Default**: `"output"`
**Example**: `"user_123_speech"`

#### `speaker_gender` (string)
The gender of the synthesized voice when not using voice cloning.

**Values**: `"male"`, `"female"`
**Default**: `"male"`

#### `pitch_shift` (number)
Adjust the pitch of the generated speech in semitones.

**Range**: `-12.0` to `12.0`
**Default**: `0.0`
**Example**: `2.5` (raises pitch by 2.5 semitones)

#### `speed_shift` (number)
Adjust the speed of the generated speech.

**Range**: `0.5` to `2.0`
**Default**: `1.0`
**Example**: `1.2` (20% faster)

#### `multi_sentence_gap` (number)
Gap between sentences in seconds.

**Range**: `0.0` to `2.0`
**Default**: `0.3`

#### `task_token` (string)
The task type for generation.

**Values**: 
- `"zero_shot"` - Generate without reference
- `"cross_lingual"` - Cross-language voice cloning
- `"continue"` - Continue from previous generation

**Default**: `"zero_shot"`

#### `temperature` (number)
Controls randomness in generation. Lower values are more deterministic.

**Range**: `0.1` to `1.0`
**Default**: `0.7`

#### `top_p` (number)
Nucleus sampling parameter. Controls diversity of generation.

**Range**: `0.1` to `1.0`
**Default**: `0.95`

#### `max_length` (integer)
Maximum number of tokens to generate.

**Range**: `256` to `8192`
**Default**: `4096`

#### `enable_whisperx` (boolean)
Generate word-level timestamps using WhisperX.

**Default**: `false`

#### `enable_subtitles` (boolean)
Generate ASS format subtitles. Requires `enable_whisperx` to be true.

**Default**: `false`

## Response Format

### Success Response (200 OK)

```json
{
  "id": "sync-12345678-90ab-cdef-1234-567890abcdef",
  "status": "COMPLETED",
  "output": {
    "status": "success",
    "audio_url": "https://bucket.s3.region.amazonaws.com/output/file_id.wav?...",
    "sample_rate": 24000,
    "duration": 5.25,
    "word_timings": [
      {
        "word": "Hello",
        "start": 0.0,
        "end": 0.5
      },
      {
        "word": "world",
        "start": 0.6,
        "end": 1.1
      }
    ],
    "subtitles_url": "https://bucket.s3.region.amazonaws.com/output/subtitles/file_id.ass?..."
  }
}
```

### Error Response

```json
{
  "id": "sync-12345678-90ab-cdef-1234-567890abcdef",
  "status": "FAILED",
  "error": "Error message describing what went wrong"
}
```

## Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| 400 | Invalid parameters | Check parameter types and ranges |
| 401 | Authentication failed | Verify API key |
| 413 | Text too long | Reduce text length or increase max_length |
| 500 | Internal server error | Retry request or contact support |
| 503 | Service unavailable | Endpoint scaling up, retry in a few seconds |

## Examples

### Basic Text-to-Speech

```bash
curl -X POST https://api.runpod.ai/v2/your-endpoint-id/runsync \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Hello, this is a test of Spark-TTS.",
      "speaker_gender": "female"
    }
  }'
```

### Voice Cloning with Reference

```bash
curl -X POST https://api.runpod.ai/v2/your-endpoint-id/runsync \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Clone this voice for the new text.",
      "prompt_text": "This is how I sound.",
      "prompt_speech_url": "s3://my-bucket/voices/reference.wav",
      "output_name": "cloned_voice"
    }
  }'
```

### With Subtitles Generation

```bash
curl -X POST https://api.runpod.ai/v2/your-endpoint-id/runsync \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Generate subtitles for this speech.",
      "enable_whisperx": true,
      "enable_subtitles": true,
      "output_name": "with_subtitles"
    }
  }'
```

### Python Example

```python
import requests
import json

endpoint_id = "your-endpoint-id"
api_key = "your-api-key"

url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "input": {
        "text": "Hello from Python!",
        "speaker_gender": "female",
        "temperature": 0.6,
        "output_name": "python_test"
    }
}

response = requests.post(url, headers=headers, json=payload)
result = response.json()

if result["status"] == "COMPLETED":
    audio_url = result["output"]["audio_url"]
    print(f"Audio generated: {audio_url}")
else:
    print(f"Error: {result.get('error')}")
```

## Rate Limits

- Default: 10 requests per second
- Burst: 50 requests
- Monthly quota: Based on your Runpod plan

## Best Practices

1. **Batch Processing**: For multiple texts, send them as separate requests but within rate limits
2. **Reference Audio**: Use high-quality, clean audio (16kHz or higher) for best voice cloning
3. **Text Preparation**: Clean text of special characters that might affect pronunciation
4. **Error Handling**: Implement exponential backoff for retries
5. **Caching**: Cache generated audio URLs as they expire after 1 hour

## Webhook Support

For async processing, use the `/run` endpoint instead of `/runsync`:

```bash
curl -X POST https://api.runpod.ai/v2/your-endpoint-id/run \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {...},
    "webhook": "https://your-server.com/webhook"
  }'
```

The webhook will receive a POST request with the result when processing completes.