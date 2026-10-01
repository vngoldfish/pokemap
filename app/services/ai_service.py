"""
AI Explanation Service for PokéTan Restock Predictions.
Provides Gemini LLM integration with automatic deterministic rule-based fallback,
strict timeouts, and in-memory TTL caching.
"""

import json
import logging
import threading
import time
from typing import Dict, Any, List, Optional, Tuple

from ..config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TIMEOUT_SECONDS,
    CHAIN_NAMES
)

logger = logging.getLogger("poketan.ai_service")

# Thread-safe in-memory cache for prediction explanations (TTL = 300 seconds / 5 minutes)
_explanation_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 300.0


def clear_explanation_cache():
    """Clear all cached explanations (useful for testing and store cache invalidation)."""
    with _cache_lock:
        _explanation_cache.clear()


def generate_rule_based_explanation(store_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure Python rule-based natural language generator.
    Guaranteed zero external network dependencies, 0ms latency, and never raises exceptions.
    Produces human-readable Vietnamese restock analysis and hunting tips.
    """
    if not isinstance(store_data, dict):
        store_data = {}

    store_id = str(store_data.get("store_id") or store_data.get("id") or "")
    store_name = str(store_data.get("name") or store_data.get("store_name") or store_id or "Cửa hàng")
    chain = str(store_data.get("chain") or "other")
    chain_name = str(store_data.get("chain_name") or CHAIN_NAMES.get(chain, chain))
    score = int(store_data.get("score") or 0)
    flash_mode = store_data.get("flash_mode") or (
        "green" if store_data.get("is_hot_30m") else ("red" if store_data.get("is_cold_30m") else "none")
    )
    truck_en_route = bool(store_data.get("truck_en_route"))

    # 1. Reasons list
    reasons: List[str] = []
    if store_data.get("reasons") and isinstance(store_data["reasons"], list):
        reasons = [str(r) for r in store_data["reasons"] if r]

    if not reasons:
        pred_window = store_data.get("predicted_window")
        if pred_window:
            reasons.append(f"Khung giờ tiềm năng cao: {pred_window}")
        dow_name = store_data.get("current_dow_name")
        if dow_name:
            reasons.append(f"Quy luật ngày {dow_name} có tần suất restock tích cực")
        avg_cycle = store_data.get("avg_interval_days")
        days_since = store_data.get("days_since_last_in")
        if avg_cycle is not None and days_since is not None:
            reasons.append(f"Chu kỳ trung bình {avg_cycle} ngày (đã qua {days_since} ngày)")
        if truck_en_route:
            reasons.append("Tín hiệu xe giao hàng cùng chuỗi đang hoạt động ở khu vực lân cận")
        if not reasons:
            reasons.append(f"Phân tích xác suất theo chuỗi {chain_name}")

    # 2. Action tip
    action_tip = str(store_data.get("action_tip") or "")
    if not action_tip:
        if flash_mode == "green" or score >= 90:
            action_tip = "🔥 Khả năng rất cao đang có hàng! Hãy đến cửa hàng ngay lập tức."
        elif flash_mode == "red" or score == 0:
            action_tip = "⛔ Kệ vừa được báo hết hàng - không nên ghé tránh lãng phí thời gian."
        elif truck_en_route:
            action_tip = "🚚 Xe giao hàng đang ở gần! Nên ghé kiểm tra kệ trong 20-45 phút tới."
        elif score >= 70:
            action_tip = "⚡ Đang trong khung giờ vàng có tỷ lệ lên kệ cao trong ngày."
        else:
            action_tip = "🕒 Canh giờ ghé vào khung giờ cao điểm để có cơ hội cao nhất."

    # 3. Concise natural language summary
    if flash_mode == "green":
        summary = f"Cửa hàng {store_name} ({chain_name}) vừa được xác nhận có hàng trong 30 phút qua. Tỷ lệ có hàng đạt 100% thời gian thực."
    elif flash_mode == "red":
        summary = f"Cửa hàng {store_name} ({chain_name}) vừa có báo cáo hết hàng trong vòng 30 phút. Tránh đến vào thời điểm này."
    elif truck_en_route:
        summary = f"Cửa hàng {store_name} ({chain_name}) ghi nhận hiệu ứng tuyến xe hàng cùng chuỗi đang giao gần đây, xác suất restock tăng vọt ({score}%)."
    elif score >= 75:
        summary = f"Cửa hàng {store_name} ({chain_name}) có điểm xác suất cao ({score}%), hội tụ chu kỳ bổ sung hàng và khung giờ cao điểm của chuỗi."
    elif score >= 50:
        summary = f"Cửa hàng {store_name} ({chain_name}) có tiềm năng restock triển vọng ({score}%), phù hợp theo dõi trong các khung giờ vàng sắp tới."
    else:
        summary = f"Cửa hàng {store_name} ({chain_name}) hiện có xác suất trung bình ({score}%). Chưa có biến động lớn về lịch sử restock gần đây."

    return {
        "status": "ok",
        "store_id": store_id,
        "store_name": store_name,
        "chain": chain,
        "score": score,
        "source": "rule_based_fallback",
        "summary": summary,
        "reasons": reasons,
        "action_tip": action_tip
    }


def _build_prediction_prompt(store_data: Dict[str, Any]) -> str:
    """Format concise structured prompt containing store logistics and historical patterns."""
    store_name = store_data.get("name") or store_data.get("store_name") or store_data.get("store_id") or "Cửa hàng"
    chain = store_data.get("chain_name") or store_data.get("chain") or "combini"
    score = int(store_data.get("score") or 0)
    current_status = store_data.get("current_status") or store_data.get("status") or "u"
    status_label = {
        "i": "🟢 Đang có hàng",
        "o": "🔴 Vừa báo hết hàng",
        "n": "⚪ Không bán thẻ",
        "u": "❔ Chưa rõ trạng thái"
    }.get(current_status, "Chưa rõ")

    predicted_window = store_data.get("predicted_window") or f"{store_data.get('predicted_hour', 11)}:00 JST"
    dow_name = store_data.get("current_dow_name") or "Hôm nay"
    avg_cycle = store_data.get("avg_interval_days") or store_data.get("turnaround_cycle") or 2.5
    days_since = store_data.get("days_since_last_in") or 0.0

    truck_ripple = (
        "Phát hiện xe giao hàng cùng chuỗi đang ở gần (~1.8km) vừa giao hàng"
        if store_data.get("truck_en_route")
        else "Không có tín hiệu xe giao hàng lân cận"
    )
    recent_min = store_data.get("recent_min_ago")
    recent_info = (
        f"Báo cáo mới nhất cách đây {recent_min} phút"
        if recent_min is not None
        else "Không có báo cáo trong 30 phút qua"
    )

    top_packs = (
        ", ".join(store_data.get("top_packs") or [])
        if store_data.get("top_packs")
        else "Chưa ghi nhận loại pack cụ thể"
    )

    prompt = f"""Bạn là trợ lý AI chuyên gia phân tích restock Pokémon TCG (PokéTan). Hãy phân tích và đưa ra nhận định ngắn gọn cho cửa hàng sau:
- Tên cửa hàng: {store_name}
- Chuỗi thương hiệu: {chain}
- Trạng thái hiện tại: {status_label}
- Điểm xác suất restock: {score}/100
- Khung giờ cao điểm dự kiến: {predicted_window}
- Thứ trong tuần: {dow_name}
- Chu kỳ bổ sung hàng trung bình: {avg_cycle} ngày (đã qua {days_since} ngày kể từ lần có hàng gần nhất)
- Tín hiệu logistics: {truck_ripple}
- Báo cáo gần đây: {recent_info}
- Loại pack hay về: {top_packs}

Yêu cầu xuất ra JSON duy nhất theo schema:
{{
  "summary": "1-2 câu nhận định tổng quan về khả năng có hàng",
  "reasons": ["Lý do phân tích 1", "Lý do phân tích 2", "Lý do phân tích 3"],
  "action_tip": "Lời khuyên hành động cụ thể cho người săn thẻ"
}}"""
    return prompt


def _call_gemini_api(prompt: str, api_key: str, model_name: str, timeout_seconds: float) -> str:
    """
    Call Google Gemini API using google.genai or google.generativeai with strict timeout.
    """
    # Try official new SDK google.genai first
    try:
        from google import genai
        from google.genai import types
        timeout_ms = int(max(0.5, timeout_seconds) * 1000)
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_ms)
        )
        config = types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=350,
            response_mime_type="application/json"
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        if resp and resp.text:
            return resp.text
    except ImportError:
        pass
    except Exception as e_genai:
        # Fallback to legacy google.generativeai if installed
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            model = legacy_genai.GenerativeModel(model_name)
            resp = model.generate_content(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 350},
                request_options={"timeout": timeout_seconds}
            )
            if resp and resp.text:
                return resp.text
        except Exception:
            raise e_genai
        raise e_genai

    # Try legacy google.generativeai directly
    import google.generativeai as legacy_genai
    legacy_genai.configure(api_key=api_key)
    model = legacy_genai.GenerativeModel(model_name)
    resp = model.generate_content(
        prompt,
        generation_config={"temperature": 0.3, "max_output_tokens": 350},
        request_options={"timeout": timeout_seconds}
    )
    if resp and resp.text:
        return resp.text
    return ""


def _parse_llm_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON object from LLM response text, handling optional markdown code fences."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(raw_text[start:end + 1])
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return None


def generate_store_prediction_explanation(store_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate an AI-powered or rule-based explanation for a store restock prediction.
    - Checks in-memory cache first (< 1ms).
    - Checks GEMINI_API_KEY. If empty/unset, immediately uses rule-based fallback.
    - If key present, calls Gemini API with timeout.
    - On any timeout, network error, or exception, logs warning and seamlessly falls back.
    - Response schema:
      {
        "status": "ok",
        "store_id": str,
        "store_name": str,
        "chain": str,
        "score": int,
        "source": "gemini" | "rule_based_fallback",
        "summary": str,
        "reasons": List[str],
        "action_tip": str
      }
    """
    if not isinstance(store_data, dict):
        store_data = {}

    store_id = str(store_data.get("store_id") or store_data.get("id") or "")
    now = time.time()

    # 1. Check in-memory cache
    if store_id:
        with _cache_lock:
            if store_id in _explanation_cache:
                cached_time, cached_res = _explanation_cache[store_id]
                if now - cached_time < _CACHE_TTL:
                    return cached_res

    # 2. Check GEMINI_API_KEY configuration
    from ..config import GEMINI_API_KEY as CURRENT_GEMINI_KEY, GEMINI_MODEL as CURRENT_MODEL, GEMINI_TIMEOUT_SECONDS as CURRENT_TIMEOUT
    api_key = (CURRENT_GEMINI_KEY or "").strip()

    if not api_key:
        fallback_res = generate_rule_based_explanation(store_data)
        if store_id:
            with _cache_lock:
                _explanation_cache[store_id] = (now, fallback_res)
        return fallback_res

    # 3. Call Gemini API with strict timeout & error handling
    try:
        prompt = _build_prediction_prompt(store_data)
        raw_text = _call_gemini_api(
            prompt=prompt,
            api_key=api_key,
            model_name=CURRENT_MODEL,
            timeout_seconds=CURRENT_TIMEOUT
        )
        parsed = _parse_llm_json(raw_text)
        if not parsed or not isinstance(parsed, dict) or "summary" not in parsed:
            raise ValueError(f"Invalid JSON response from Gemini: {raw_text[:100] if raw_text else 'None'}")

        reasons = parsed.get("reasons")
        if not isinstance(reasons, list) or not reasons:
            reasons = store_data.get("reasons") or [str(parsed.get("summary"))]
        else:
            reasons = [str(r) for r in reasons]

        summary = str(parsed.get("summary") or "")
        action_tip = str(parsed.get("action_tip") or store_data.get("action_tip") or "")
        score = int(store_data.get("score") or 0)
        chain = str(store_data.get("chain") or "other")
        store_name = str(store_data.get("name") or store_data.get("store_name") or store_id or "Cửa hàng")

        result = {
            "status": "ok",
            "store_id": store_id,
            "store_name": store_name,
            "chain": chain,
            "score": score,
            "source": "gemini",
            "summary": summary,
            "reasons": reasons,
            "action_tip": action_tip
        }

        if store_id:
            with _cache_lock:
                _explanation_cache[store_id] = (now, result)
        return result

    except Exception as e:
        logger.warning(
            "Gemini explanation failed for store '%s' (model=%s, timeout=%ss): %s. Falling back to rule-based.",
            store_id, CURRENT_MODEL, CURRENT_TIMEOUT, e
        )
        fallback_res = generate_rule_based_explanation(store_data)
        if store_id:
            with _cache_lock:
                _explanation_cache[store_id] = (now, fallback_res)
        return fallback_res
