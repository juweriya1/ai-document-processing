retry_policy GeminiBackoff {
    max_retries 3
    strategy {
        type exponential_backoff
        delay_ms 500
        multiplier 2
        max_delay_ms 8000
    }
}

// Primary model — gemini-2.5-flash has the highest accuracy but occasionally
// 503s under load. Retries 3× with backoff before giving up.
client<llm> GeminiFlashPrimary {
    provider "google-ai"
    options {
        model "gemini-2.5-flash"
        api_key env.GOOGLE_API_KEY
    }
    retry_policy GeminiBackoff
}

// Fallback model — gemini-2.5-flash-lite runs on a less-contested endpoint
// (same Gemini family, smaller parameter count, same JSON schema handling).
// Used automatically when the primary exhausts its retries.
client<llm> GeminiFlashLite {
    provider "google-ai"
    options {
        model "gemini-2.5-flash-lite"
        api_key env.GOOGLE_API_KEY
    }
    retry_policy GeminiBackoff
}

// Public client name consumed by extraction.baml. The fallback provider
// transparently routes to GeminiFlashLite if GeminiFlashPrimary exhausts
// its retry budget — so pipeline code never sees the 503.
client<llm> GeminiFlash {
    provider fallback
    options {
        strategy [
            GeminiFlashPrimary,
            GeminiFlashLite
        ]
    }
}
