import requests
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from pathlib import Path
import json

load_dotenv()
KOBIS_API_KEY = os.environ.get("KOBIS_API_KEY")
KOBIS_WEEKLY_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchWeeklyBoxOfficeList.json"

cache = {"date" : None, "data" : None}

app = Flask(__name__)
CORS(app)

@app.route("/api/boxoffice", methods=['GET'])
def boxoffice():
    if not KOBIS_API_KEY:
        return jsonify({"status": "error", "message" : "KOBIS API 키 값이 설정되지 않았습니다."}), 500
    
    yesterday = datetime.now() - timedelta(days=1)
    KOBIS_TIME_FORMAT = yesterday.strftime("%Y%m%d")
    
    if cache["date"] == KOBIS_TIME_FORMAT and cache["data"] is not None:
        return jsonify({"status": "success", "cached" : True, "movies": cache["data"]}), 200
    else:
        try:
            kobis_data = fetch_KOBIS(KOBIS_TIME_FORMAT)
            metadata = load_metadata()
            movies = format_movies(kobis_data, metadata)
            
            cache["date"] = KOBIS_TIME_FORMAT
            cache["data"] = movies
            
            return jsonify({"status": "success", "cached": False, "movies": movies}), 200
        
        except requests.exceptions.RequestException as e:
            return jsonify({"status": "error", "message": f"KOBIS API 호출 실패: {str(e)}"}), 502
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
            
def fetch_KOBIS(KOBIS_TIME_FORMAT: str):
    params = {
        "key": KOBIS_API_KEY,
        "targetDt": KOBIS_TIME_FORMAT,
        "weekGb": "0",
    }
    r = requests.get(KOBIS_WEEKLY_URL, params = params, timeout = 10)
    r.raise_for_status()
    return r.json()

def load_metadata():
    METADATA_PATH = Path(__file__).parent / "movie_metadata.json"
    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

def format_movies(kobis_response: dict, metadata: dict, top_n: int = 6):
    movies = []
      
    if "boxOfficeResult" in kobis_response:
        box_office_result = kobis_response["boxOfficeResult"]
        if "weeklyBoxOfficeList" in box_office_result:
            box_list = box_office_result["weeklyBoxOfficeList"]
        else:
            box_list = []
    else:
        box_list = []

    idx = 0
    for movie in box_list[:top_n]:
        movie_cd = movie.get("movieCd", "")
        meta = metadata.get(movie_cd, {})
          
        open_dt = movie.get("openDt", "").replace("-", "")
        if len(open_dt) == 8:
            year  = open_dt[0:4]
            month = open_dt[4:6]
            day   = open_dt[6:8]
            release_date = year + "-" + month + "-" + day
        else:
            release_date = "미정"

        try:
            audience_number = int(movie.get("audiAcc", "0"))
            audience = format(audience_number, ",")
        except ValueError:
            audience = "0"
        except TypeError:
            audience = "0"

        movies.append({
            "movie_index": idx,
            "rank": int(movie.get("rank", idx + 1)),
            "title": movie.get("movieNm", ""),
            "rating": meta.get("rating", "N/A"),
            "audience": audience,
            "release_date": release_date,
            "image": meta.get("image", "/images/placeholder.webp"),
            "movie_cd": movie_cd,
        })

        idx = idx + 1

    return movies

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "boxoffice"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
            
    
    
    
