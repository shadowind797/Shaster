**Test Case ID:** SPOT-PL-001  
**Title:** Verify Creation and Renaming of a New Playlist on Spotify  
**Preconditions:**  
- Tester is using a supported web browser (e.g., Chrome, Firefox) with a stable internet connection.  
- Tester has valid Spotify credentials:  
  - **Username:** shaster78953@gmail.com  
  - **Password:** AgentCool007  
- Tester has access to the Spotify login page (https://accounts.spotify.com/en/login) and the Spotify Web Player (https://open.spotify.com/).

---

**Test Steps:**

1. **Open Browser & Navigate:**  
   - Launch your web browser and navigate to [https://accounts.spotify.com/en/login].

2. **Login:**  
   - In the "Username" field, enter: **shaster78953@gmail.com**.  
   - In the "Password" field, enter: **AgentCool007**.  
   - Click the **Log In** button.  
   - **Expected Result:** The Spotify dashboard loads, indicating a successful login.

3. **Access Web Player:**
   - Click the **Web Player** link.
   - Wait for redirect to the Spotify Web Player. If not automatically redirected, navigate to [https://open.spotify.com/].  
   - **Expected Result:** The Spotify Web Player displays your music library and navigation sidebar.

4. **Create a New Playlist:**  
   - In the left sidebar, locate and click the **Create playlist** button.  
   - **Expected Result:** A new playlist is created with a default name (e.g., "My Playlist") and appears in your list of playlists.

5. **Rename the Playlist:**   
   - Locate the playlist title and click it to enable editing.  
   - Clear the default name and type in **Test Playlist**.  
   - Press **Enter** or click **Save** button to save the new name.  
   - **Expected Result:** The playlist name is updated to **Test Playlist**.

6. **Verify Playlist Details:**  
   - Confirm that the renamed playlist now appears in your library with the correct name.  
   - Optionally, check for additional options (like adding a description) if available.

---

**Postconditions:**  
- The Spotify account now includes a playlist named **Test Playlist**.
