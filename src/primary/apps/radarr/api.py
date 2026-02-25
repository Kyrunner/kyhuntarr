#!/usr/bin/env python3
"""
Radarr-specific API functions
Handles all communication with the Radarr API
"""

import requests
import json
import sys
import time
import random
import traceback
from typing import List, Dict, Any, Optional, Union

# Correct the import path
from src.primary.utils.logger import get_logger
from src.primary.settings_manager import get_ssl_verify_setting

# Get logger for the Radarr app
radarr_logger = get_logger("radarr")

# Use a session for better performance
session = requests.Session()


def arr_request(
    api_url: str,
    api_key: str,
    api_timeout: int,
    endpoint: str,
    method: str = "GET",
    data: Dict = None,
) -> Any:
    """
    Make a request to the Radarr API.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        endpoint: The API endpoint to call (without /api/v3/)
        method: HTTP method (GET, POST, PUT, DELETE)
        data: Optional data payload for POST/PUT requests

    Returns:
        The parsed JSON response or None if the request failed
    """
    try:
        if not api_url or not api_key:
            radarr_logger.error("No URL or API key provided")
            return None

        # Construct the full URL properly
        full_url = f"{api_url.rstrip('/')}/api/v3/{endpoint.lstrip('/')}"

        radarr_logger.debug(f"Making {method} request to: {full_url}")

        # Set up headers with the API key
        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "KYHUNTARR/1.0 (https://github.com/Kyrunner/kyhuntarr)",
        }

        # Get SSL verification setting
        verify_ssl = get_ssl_verify_setting()

        if not verify_ssl:
            radarr_logger.debug("SSL verification disabled by user setting")

        # Make the request based on the method
        if method.upper() == "GET":
            response = session.get(
                full_url, headers=headers, timeout=api_timeout, verify=verify_ssl
            )
        elif method.upper() == "POST":
            response = session.post(
                full_url,
                headers=headers,
                json=data,
                timeout=api_timeout,
                verify=verify_ssl,
            )
        elif method.upper() == "PUT":
            response = session.put(
                full_url,
                headers=headers,
                json=data,
                timeout=api_timeout,
                verify=verify_ssl,
            )
        elif method.upper() == "DELETE":
            response = session.delete(
                full_url, headers=headers, timeout=api_timeout, verify=verify_ssl
            )
        else:
            radarr_logger.error(f"Unsupported HTTP method: {method}")
            return None

        # Check for errors
        response.raise_for_status()

        # Parse JSON response
        if response.text:
            return response.json()
        return {}

    except requests.exceptions.RequestException as e:
        radarr_logger.error(f"API request failed: {e}")
        return None


def get_download_queue_size(api_url: str, api_key: str, api_timeout: int) -> int:
    """
    Get the current size of the download queue.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request

    Returns:
        The number of items in the download queue, or -1 if the request failed
    """
    if not api_url or not api_key:
        radarr_logger.error(
            "Radarr API URL or API Key not provided for queue size check."
        )
        return -1
    try:
        # Radarr uses /api/v3/queue
        endpoint = f"{api_url.rstrip('/')}/api/v3/queue?page=1&pageSize=1000"  # Fetch a large page size
        headers = {"X-Api-Key": api_key}
        response = session.get(endpoint, headers=headers, timeout=api_timeout)
        response.raise_for_status()
        queue_data = response.json()
        queue_size = queue_data.get("totalRecords", 0)
        radarr_logger.debug(f"Radarr download queue size: {queue_size}")
        return queue_size
    except requests.exceptions.RequestException as e:
        radarr_logger.error(f"Error getting Radarr download queue size: {e}")
        return -1  # Return -1 to indicate an error
    except Exception as e:
        radarr_logger.error(
            f"An unexpected error occurred while getting Radarr queue size: {e}"
        )
        return -1


def get_movies_with_missing(
    api_url: str, api_key: str, api_timeout: int, monitored_only: bool
) -> Optional[List[Dict]]:
    """
    Get a list of movies with missing files (not downloaded/available).

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored movies.

    Returns:
        A list of movie objects with missing files, or None if the request failed.
    """
    # Use the updated arr_request with passed arguments
    movies = arr_request(api_url, api_key, api_timeout, "movie")
    if movies is None:  # Check for None explicitly, as an empty list is valid
        radarr_logger.error("Failed to retrieve movies from Radarr API.")
        return None

    missing_movies = []
    for movie in movies:
        is_monitored = movie.get("monitored", False)
        has_file = movie.get("hasFile", False)
        # Apply monitored_only filter if requested
        if not has_file and (not monitored_only or is_monitored):
            missing_movies.append(movie)

    radarr_logger.debug(
        f"Found {len(missing_movies)} missing movies (monitored_only={monitored_only})."
    )
    return missing_movies


def get_cutoff_unmet_movies(
    api_url: str, api_key: str, api_timeout: int, monitored_only: bool
) -> Optional[List[Dict]]:
    """
    Get a list of movies that don't meet their quality profile cutoff.

    Uses Radarr's native /api/v3/wanted/cutoff endpoint which correctly evaluates
    both quality rank AND custom format scores against the profile's cutoffFormatScore.
    This matches how Sonarr and Lidarr already work in this codebase.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored movies.

    Returns:
        A list of movie objects that need quality upgrades, or None if the request failed.
    """
    endpoint = "wanted/cutoff"
    page = 1
    page_size = 1000
    all_cutoff_unmet = []
    retries_per_page = 2
    retry_delay = 3

    radarr_logger.debug(
        f"Starting fetch for cutoff unmet movies (monitored_only={monitored_only})."
    )

    while True:
        retry_count = 0
        success = False
        records = []

        while retry_count <= retries_per_page and not success:
            params = {
                "page": page,
                "pageSize": page_size,
                "sortKey": "title",
                "sortDir": "asc",
            }
            url = f"{api_url.rstrip('/')}/api/v3/{endpoint}"
            radarr_logger.debug(
                f"Requesting cutoff unmet page {page} "
                f"(attempt {retry_count + 1}/{retries_per_page + 1})"
            )

            try:
                response = requests.get(
                    url,
                    headers={"X-Api-Key": api_key},
                    params=params,
                    timeout=api_timeout,
                )
                radarr_logger.debug(
                    f"Radarr API response status code for cutoff unmet "
                    f"page {page}: {response.status_code}"
                )
                response.raise_for_status()

                if not response.content:
                    radarr_logger.warning(
                        f"Empty response for cutoff unmet movies page {page} "
                        f"(attempt {retry_count + 1})"
                    )
                    if retry_count < retries_per_page:
                        retry_count += 1
                        time.sleep(retry_delay)
                        continue
                    else:
                        radarr_logger.error(
                            f"Giving up on empty response after "
                            f"{retries_per_page + 1} attempts"
                        )
                        break

                try:
                    data = response.json()
                    records = data.get("records", [])
                    total_records_on_page = len(records)
                    total_records_reported = data.get("totalRecords", 0)

                    if page == 1:
                        radarr_logger.info(
                            f"Radarr API reports {total_records_reported} "
                            f"total cutoff unmet movies."
                        )

                    radarr_logger.debug(
                        f"Parsed {total_records_on_page} cutoff unmet "
                        f"records from page {page}"
                    )

                    if not records:
                        radarr_logger.debug(
                            f"No more cutoff unmet records found on "
                            f"page {page}. Stopping pagination."
                        )
                        success = True
                        break

                    all_cutoff_unmet.extend(records)

                    if total_records_on_page < page_size:
                        radarr_logger.debug(
                            f"Received {total_records_on_page} records "
                            f"(less than page size {page_size}). Last page."
                        )
                        success = True
                        break

                    success = True
                    break

                except json.JSONDecodeError as e:
                    radarr_logger.error(
                        f"Failed to decode JSON for cutoff unmet page {page} "
                        f"(attempt {retry_count + 1}): {e}"
                    )
                    if retry_count < retries_per_page:
                        retry_count += 1
                        time.sleep(retry_delay)
                        continue
                    else:
                        radarr_logger.error(
                            f"Giving up after {retries_per_page + 1} "
                            f"failed JSON decode attempts"
                        )
                        break

            except requests.exceptions.Timeout as e:
                radarr_logger.error(
                    f"Timeout for cutoff unmet page {page} "
                    f"(attempt {retry_count + 1}): {e}"
                )
                if retry_count < retries_per_page:
                    retry_count += 1
                    time.sleep(retry_delay * 2)
                    continue
                else:
                    radarr_logger.error(
                        f"Giving up after {retries_per_page + 1} timeout failures"
                    )
                    break

            except requests.exceptions.RequestException as e:
                radarr_logger.error(
                    f"Request error for cutoff unmet page {page} "
                    f"(attempt {retry_count + 1}): {e}"
                )
                if retry_count < retries_per_page:
                    retry_count += 1
                    time.sleep(retry_delay)
                    continue
                else:
                    radarr_logger.error(
                        f"Giving up on request after "
                        f"{retries_per_page + 1} failed attempts"
                    )
                    break

            except Exception as e:
                radarr_logger.error(
                    f"Unexpected error for cutoff unmet page {page} "
                    f"(attempt {retry_count + 1}): {e}"
                )
                if retry_count < retries_per_page:
                    retry_count += 1
                    time.sleep(retry_delay)
                    continue
                else:
                    radarr_logger.error(
                        f"Giving up after unexpected error and "
                        f"{retries_per_page + 1} attempts"
                    )
                    break

        if not success or not records:
            break

        page += 1

    radarr_logger.info(
        f"Total cutoff unmet movies fetched across all pages: {len(all_cutoff_unmet)}"
    )

    if monitored_only:
        original_count = len(all_cutoff_unmet)
        filtered_cutoff_unmet = [
            movie for movie in all_cutoff_unmet if movie.get("monitored", False)
        ]
        radarr_logger.debug(
            f"Filtered for monitored_only=True: {len(filtered_cutoff_unmet)} "
            f"monitored cutoff unmet movies remain "
            f"(out of {original_count} total)."
        )
        return filtered_cutoff_unmet
    else:
        radarr_logger.debug(
            f"Returning {len(all_cutoff_unmet)} cutoff unmet movies "
            f"(monitored_only=False)."
        )
        return all_cutoff_unmet


def get_cutoff_unmet_movies_random_page(
    api_url: str,
    api_key: str,
    api_timeout: int,
    monitored_only: bool,
    count: int,
) -> List[Dict[str, Any]]:
    """
    Get a specified number of random cutoff unmet movies by selecting a random page.
    This is much more efficient for very large libraries than fetching all movies.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: Whether to include only monitored movies
        count: How many movies to return

    Returns:
        A list of randomly selected cutoff unmet movies
    """
    endpoint = "wanted/cutoff"
    page_size = 100

    params = {
        "page": 1,
        "pageSize": 1,
    }
    url = f"{api_url.rstrip('/')}/api/v3/{endpoint}"

    try:
        response = requests.get(
            url,
            headers={"X-Api-Key": api_key},
            params=params,
            timeout=api_timeout,
        )
        response.raise_for_status()
        data = response.json()
        total_records = data.get("totalRecords", 0)

        if total_records == 0:
            radarr_logger.info("No cutoff unmet movies found in Radarr.")
            return []

        total_pages = (total_records + page_size - 1) // page_size
        radarr_logger.info(
            f"Found {total_records} total cutoff unmet movies "
            f"across {total_pages} pages"
        )

        if total_pages == 0:
            return []

        random_page = random.randint(1, total_pages)
        radarr_logger.info(
            f"Selected random page {random_page} of {total_pages} "
            f"for quality upgrade selection"
        )

        params = {
            "page": random_page,
            "pageSize": page_size,
        }

        response = requests.get(
            url,
            headers={"X-Api-Key": api_key},
            params=params,
            timeout=api_timeout,
        )
        response.raise_for_status()

        data = response.json()
        records = data.get("records", [])
        radarr_logger.info(f"Retrieved {len(records)} movies from page {random_page}")

        if monitored_only:
            filtered_records = [
                movie for movie in records if movie.get("monitored", False)
            ]
            radarr_logger.debug(f"Filtered to {len(filtered_records)} monitored movies")
            records = filtered_records

        if len(records) > count:
            selected_records = random.sample(records, count)
            radarr_logger.debug(
                f"Randomly selected {len(selected_records)} movies "
                f"from page {random_page}"
            )
            return selected_records
        else:
            radarr_logger.debug(
                f"Returning all {len(records)} movies from "
                f"page {random_page} (fewer than requested {count})"
            )
            return records

    except requests.exceptions.RequestException as e:
        radarr_logger.error(
            f"Error getting random cutoff unmet movies from Radarr: {str(e)}"
        )
        return []
    except json.JSONDecodeError as e:
        radarr_logger.error(
            f"Failed to decode JSON response for random cutoff selection: {str(e)}"
        )
        return []
    except Exception as e:
        radarr_logger.error(f"Unexpected error in random cutoff selection: {str(e)}")
        return []


def get_cf_upgrade_movies(
    api_url: str, api_key: str, api_timeout: int, monitored_only: bool
) -> Optional[List[Dict]]:
    """
    Get movies that meet their quality cutoff but have custom format scores
    below the profile's cutoffFormatScore (Upgrade Until Custom score).

    Radarr's wanted/cutoff endpoint does NOT flag these movies as cutoff-unmet.
    This function fills that gap by checking CF scores client-side for profiles
    that use cutoffFormatScore (typically TRaSH Guides profiles with a value of 10000).

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        monitored_only: If True, only return monitored movies.

    Returns:
        A list of movie objects eligible for CF score upgrades, or None on failure.
    """
    radarr_logger.debug(
        "Checking for movies eligible for custom format score upgrades..."
    )

    # Step 1: Fetch quality profiles and identify those with cutoffFormatScore > 0
    profiles = arr_request(api_url, api_key, api_timeout, "qualityprofile")
    if profiles is None:
        radarr_logger.error("Failed to retrieve quality profiles from Radarr API.")
        return None

    cf_profiles = {}
    for p in profiles:
        cutoff_fs = p.get("cutoffFormatScore", 0)
        if cutoff_fs > 0 and p.get("upgradeAllowed", False):
            cf_profiles[p["id"]] = cutoff_fs

    if not cf_profiles:
        radarr_logger.debug(
            "No quality profiles with cutoffFormatScore > 0 found. "
            "Skipping CF upgrade check."
        )
        return []

    radarr_logger.debug(
        f"Found {len(cf_profiles)} profiles with cutoffFormatScore: {cf_profiles}"
    )

    # Step 2: Fetch all movies and filter to those on CF profiles with files
    movies = arr_request(api_url, api_key, api_timeout, "movie")
    if movies is None:
        radarr_logger.error("Failed to retrieve movies from Radarr API.")
        return None

    candidates = []
    for movie in movies:
        if monitored_only and not movie.get("monitored", False):
            continue
        if not movie.get("hasFile", False):
            continue
        pid = movie.get("qualityProfileId")
        if pid not in cf_profiles:
            continue
        mf = movie.get("movieFile", {})
        if not mf or not mf.get("id"):
            continue
        # Skip movies already flagged as cutoff-unmet by Radarr
        # (those are handled by get_cutoff_unmet_movies)
        if mf.get("qualityCutoffNotMet", False):
            continue
        candidates.append(movie)

    radarr_logger.debug(
        f"Found {len(candidates)} candidate movies on CF profiles "
        f"that meet quality cutoff."
    )

    if not candidates:
        return []

    # Step 3: Fetch CF scores via moviefile endpoint and compare
    upgrade_movies = []
    verify_ssl = get_ssl_verify_setting()
    headers = {"X-Api-Key": api_key}

    for movie in candidates:
        mf = movie.get("movieFile", {})
        movie_id = movie.get("id")
        mf_id = mf.get("id")
        pid = movie.get("qualityProfileId")
        target_score = cf_profiles[pid]

        try:
            url = f"{api_url.rstrip('/')}/api/v3/moviefile?movieId={movie_id}"
            response = session.get(
                url, headers=headers, timeout=api_timeout, verify=verify_ssl
            )
            response.raise_for_status()
            files = response.json()

            if files and isinstance(files, list):
                for f in files:
                    cf_score = f.get("customFormatScore", 0)
                    if cf_score is None:
                        cf_score = 0
                    if cf_score < target_score:
                        quality_name = (
                            f.get("quality", {})
                            .get("quality", {})
                            .get("name", "unknown")
                        )
                        radarr_logger.debug(
                            f"CF upgrade candidate: {movie.get('title')} "
                            f"({movie.get('year')}) - {quality_name} - "
                            f"CF Score: {cf_score}/{target_score}"
                        )
                        upgrade_movies.append(movie)
                        break
        except requests.exceptions.RequestException as e:
            radarr_logger.debug(
                f"Failed to fetch moviefile for movie ID {movie_id}: {e}"
            )
            continue
        except Exception as e:
            radarr_logger.debug(
                f"Unexpected error checking CF score for movie ID {movie_id}: {e}"
            )
            continue

    radarr_logger.info(
        f"Found {len(upgrade_movies)} movies eligible for custom format "
        f"score upgrades (CF score below profile cutoffFormatScore)."
    )
    return upgrade_movies


def refresh_movie(
    api_url: str,
    api_key: str,
    api_timeout: int,
    movie_id: int,
    command_wait_delay: int = 1,
    command_wait_attempts: int = 600,
) -> Optional[int]:
    """
    Refresh functionality has been removed as it was a performance bottleneck.
    This function now returns a placeholder success value without making any API calls.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        movie_id: The ID of the movie to refresh
        command_wait_delay: Seconds to wait between command status checks
        command_wait_attempts: Maximum number of status check attempts

    Returns:
        A placeholder command ID (123) to simulate success
    """
    radarr_logger.debug(f"Refresh functionality disabled for movie ID: {movie_id}")
    # Return a placeholder command ID (123) to simulate success without actually refreshing
    return 123


def movie_search(
    api_url: str, api_key: str, api_timeout: int, movie_ids: List[int]
) -> Optional[int]:
    """
    Trigger a search for one or more movies.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        movie_ids: A list of movie IDs to search for

    Returns:
        The command ID if the search command was triggered successfully, None otherwise
    """
    if not movie_ids:
        radarr_logger.warning("No movie IDs provided for search.")
        return None

    endpoint = "command"
    data = {"name": "MoviesSearch", "movieIds": movie_ids}

    # Use the updated arr_request
    response = arr_request(
        api_url, api_key, api_timeout, endpoint, method="POST", data=data
    )
    if response and "id" in response:
        command_id = response["id"]
        radarr_logger.debug(
            f"Triggered search for movie IDs: {movie_ids}. Command ID: {command_id}"
        )
        return command_id
    else:
        radarr_logger.error(
            f"Failed to trigger search command for movie IDs {movie_ids}. Response: {response}"
        )
        return None


def check_connection(api_url: str, api_key: str, api_timeout: int) -> bool:
    """Check the connection to Radarr API."""
    try:
        # Ensure api_url is properly formatted
        if not api_url:
            radarr_logger.error("API URL is empty or not set")
            return False

        # Make sure api_url has a scheme
        if not (api_url.startswith("http://") or api_url.startswith("https://")):
            radarr_logger.error(
                f"Invalid URL format: {api_url} - URL must start with http:// or https://"
            )
            return False

        # Ensure URL doesn't end with a slash before adding the endpoint
        base_url = api_url.rstrip("/")
        full_url = f"{base_url}/api/v3/system/status"

        response = requests.get(
            full_url, headers={"X-Api-Key": api_key}, timeout=api_timeout
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        radarr_logger.debug("Successfully connected to Radarr.")
        return True
    except requests.exceptions.RequestException as e:
        radarr_logger.error(f"Error connecting to Radarr: {e}")
        return False
    except Exception as e:
        radarr_logger.error(
            f"An unexpected error occurred during Radarr connection check: {e}"
        )
        return False


def wait_for_command(
    api_url: str,
    api_key: str,
    api_timeout: int,
    command_id: int,
    delay_seconds: int = 1,
    max_attempts: int = 600,
) -> bool:
    """
    Wait for a command to complete.

    Args:
        api_url: The base URL of the Radarr API
        api_key: The API key for authentication
        api_timeout: Timeout for the API request
        command_id: The ID of the command to wait for
        delay_seconds: Seconds to wait between command status checks
        max_attempts: Maximum number of status check attempts

    Returns:
        True if the command completed successfully, False if timed out
    """
    attempts = 0
    while attempts < max_attempts:
        response = arr_request(api_url, api_key, api_timeout, f"command/{command_id}")
        if response and "state" in response:
            state = response["state"]
            if state == "completed":
                return True
            elif state == "failed":
                radarr_logger.error(f"Command {command_id} failed")
                return False
        time.sleep(delay_seconds)
        attempts += 1
    radarr_logger.warning(f"Timed out waiting for command {command_id} to complete")
    return False
