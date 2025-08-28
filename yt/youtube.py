import webview
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
API_KEY = "AIzaSyAav6iqs8d6XyLztW2oGeiR5rv2kNJW6JI"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

def play_video_in_window(video_id: str, title: str = "YouTube Video"):
    """
    Opens a given YouTube video ID in a pywebview window.
    """
    embed_url = f"https://www.youtube.com/embed/{video_id}"
    print(f" Success! Opening '{title}' in a new window...")
    try:
        webview.create_window(title, embed_url, width=800, height=600, resizable=True)
        webview.start()
    except Exception as e:
        print(f"An error occurred while trying to open the window: {e}")

def play_from_search():
    """
    to play top search result from user input.
    """
    query = input("Enter what you want to search for:\n> ")
    if not query.strip():
        print(" Search query cannot be empty.")
        return


    try:
        print("\nConnecting to YouTube API...")
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
        
        play_video_in_window(video_id, video_title)

    except HttpError as e:
        print(f"\nAn API error occurred: {e}")
        print("   Please check that your API key is correct and that you have not exceeded your daily quota.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

def play_from_url():
    """
    Prompts the user for a YouTube URL,and plays the video.
    """
    url = input("Please paste the full YouTube video URL:\n> ")
    if not url.strip():
        print("URL cannot be empty.")
        return

    
    regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(regex, url)
    
    if match:
        video_id = match.group(1)
        
        play_video_in_window(video_id, "YouTube Video")
    else:
        print(" Invalid YouTube URL. Please make sure it's a correct and complete link.")

def main():
    print("Welcome to the Python YouTube Player!")
    print("=" * 50)

    while True:
        print("\nChoose an option:")
        print("  1. Search for a video by keyword")
        print("  2. Play a video from a URL")
        print("  3. Exit")
        
        choice = input("Enter your choice (1, 2, or 3): ")

        if choice == '1':
            play_from_search()
        elif choice == '2':
            play_from_url()
        elif choice == '3':
            print("\n Goodbye!")
            break
        else:
            print("\nInvalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
