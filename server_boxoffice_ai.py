# server_boxoffice.py
# 박스오피스 조회 전용 Flask 서버 (가벼움, 클라우드 배포용)
#
# 역할:
#   1. KOBIS 영화진흥위원회 API에서 주간 박스오피스 Top N 가져오기
#   2. 수동 작성한 movie_metadata.json과 결합 (포스터 경로, 평점 등)
#   3. 프론트엔드(MainPage.jsx의 MovieCard)가 바로 쓸 수 있는 형태로 가공해 응답
#   4. 같은 날짜 재요청 시 캐싱

from flask import Flask, jsonify
from flask_cors import CORS
import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # 로컬 개발 시 .env 파일 로드. Render 등에서는 환경변수가 직접 주입됨

app = Flask(__name__)
CORS(app)  # 운영 환경에서는 origins=["https://multiflex-crawling-project.vercel.app"]처럼 좁히는 게 안전

KOBIS_API_KEY = os.environ.get("KOBIS_API_KEY")
KOBIS_WEEKLY_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchWeeklyBoxOfficeList.json"

METADATA_PATH = Path(__file__).parent / "movie_metadata.json"

# 메모리 캐시. 하루에 한 번만 KOBIS 호출하면 충분함
_cache = {"date": None, "data": None}


def _load_metadata() -> dict:
    """수동 작성된 영화 메타데이터(포스터 경로, 평점) 로드"""
    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _get_target_date() -> str:
    """KOBIS 박스오피스용 날짜. 어제 날짜를 yyyymmdd 형식으로 반환.
    KOBIS는 오늘 데이터를 아직 집계 안 했으므로 어제 기준."""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")


def _fetch_kobis_weekly(target_dt: str) -> dict:
    """KOBIS 주간 박스오피스 API 호출.
    weekGb: 0=주간(월~일), 1=주말(금~일), 2=주중(월~목)"""
    params = {
        "key": KOBIS_API_KEY,
        "targetDt": target_dt,
        "weekGb": "0",
    }
    response = requests.get(KOBIS_WEEKLY_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def _format_movies(kobis_response: dict, metadata: dict, top_n: int = 6) -> list:
    """KOBIS 응답 + 메타데이터 결합 → MainPage.jsx의 MOVIES 배열 스키마와 동일한 형태로 가공"""
    movies = []
    box_list = kobis_response.get("boxOfficeResult", {}).get("weeklyBoxOfficeList", [])

    for idx, movie in enumerate(box_list[:top_n]):
        movie_cd = movie.get("movieCd", "")
        meta = metadata.get(movie_cd, {})

        # 개봉일 형식 통일 (yyyymmdd → yyyy-mm-dd)
        open_dt = movie.get("openDt", "").replace("-", "")
        if len(open_dt) == 8:
            release_date = f"{open_dt[:4]}-{open_dt[4:6]}-{open_dt[6:]}"
        else:
            release_date = "미정"

        # 누적 관객 수 천 단위 콤마 (1234567 → "1,234,567")
        try:
            audience = f"{int(movie.get('audiAcc', '0')):,}"
        except (ValueError, TypeError):
            audience = "0"

        movies.append({
            "movie_index": idx,
            "rank": int(movie.get("rank", idx + 1)),
            "title": movie.get("movieNm", ""),
            "rating": meta.get("rating", "N/A"),
            "audience": audience,
            "release_date": release_date,
            "image": meta.get("image", "/images/placeholder.webp"),
            "movie_cd": movie_cd,  # 메타데이터 매핑 누락된 영화 식별용. 시연 전 콘솔에서 확인하세요
        })

    return movies


@app.route("/api/boxoffice", methods=["GET"])
def boxoffice():
    """주간 박스오피스 Top 6 반환.
    응답 예시:
    {
        "status": "success",
        "cached": false,
        "movies": [
            {"movie_index": 0, "rank": 1, "title": "...", "rating": "...",
             "audience": "...", "release_date": "...", "image": "...", "movie_cd": "..."},
            ...
        ]
    }"""
    if not KOBIS_API_KEY:
        return jsonify({"status": "error", "message": "KOBIS_API_KEY 환경변수가 설정되지 않았습니다."}), 500

    target_dt = _get_target_date()

    # 같은 날짜 재요청 시 캐싱 응답
    if _cache["date"] == target_dt and _cache["data"] is not None:
        return jsonify({"status": "success", "cached": True, "movies": _cache["data"]})

    try:
        kobis_data = _fetch_kobis_weekly(target_dt)
        metadata = _load_metadata()
        movies = _format_movies(kobis_data, metadata)

        _cache["date"] = target_dt
        _cache["data"] = movies

        return jsonify({"status": "success", "cached": False, "movies": movies})

    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"KOBIS API 호출 실패: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "boxoffice"})


if __name__ == "__main__":
    # 5000번 포트는 동료의 크롤링 서버와 충돌할 수 있으니 5001 사용
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)