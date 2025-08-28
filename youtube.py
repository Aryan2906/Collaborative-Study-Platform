import webview
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


API_KEY = "AIzaSyAav6iqs8d6XyLztW2oGeiR5rv2kNJW6JI"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

def play_top_youtube_result(query):
    """
    Searches for a query on YouTube using the official API and opens the
    top result in a standalone pywebview window.

    Args:
        query (str): The search term provided by the user.
    """
    if API_KEY != "AIzaSyAav6iqs8d6XyLztW2oGeiR5rv2kNJW6JI":
        print("ERROR: Please replace API key with your actual YouTube Data API key.")
        return

    try:
       
        print("Connecting to YouTube API...")
        youtube_service = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)

        
        print(f"Searching for '{query}'...")
        search_response = youtube_service.search().list(
            q=query,
            part="snippet",  
            maxResults=1,   
            type="video"     
        ).execute()

        
        results = search_response.get("items", [])
        
        if not results:
            print("Sorry, no video results were found for that query. Please try another.")
            return

        
        top_result = results[0]
        video_id = top_result["id"]["videoId"]
        video_title = top_result["snippet"]["title"]
        
        
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        
        print(f"Found: '{video_title}'")
        print("Opening in a new window...")
        
        webview.create_window(video_title, video_url, width=800, height=600)
        webview.start()

    except HttpError as e:
        
        print(f"\nAn API error occurred: {e}")
        print("Please check that your API key is correct and that you have not exceeded your daily quota.")
    except Exception as e:
        
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    user_query = input("Enter what you want to watch on YouTube: ")

    if user_query.strip():
        play_top_youtube_result(user_query)
    else:
        print("Search query cannot be empty. Please run the script again.")