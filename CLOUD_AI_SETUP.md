# Cloud AI Provider Setup

## Groq
1. Get API key from [Groq Console](https://console.groq.com/)
2. Add to `.env`:
```env
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama3-8b-8192
```

## HuggingFace
1. Get API key from [HuggingFace Hub](https://huggingface.co/settings/tokens)
2. Add to `.env`:
```env
HUGGINGFACE_API_KEY=your_key_here
HF_MODEL=meta-llama/Llama-3-8b
```

## Replicate
1. Get API token from [Replicate Dashboard](https://replicate.com/account/api-tokens)
2. Add to `.env`:
```env
REPLICATE_API_TOKEN=your_token_here
REPLICATE_MODEL=meta/llama-3-8b-instruct
```

> **Note**: Create `.env` file in backend/ directory with these values