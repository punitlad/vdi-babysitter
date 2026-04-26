# Debugging 
## Scenario 1: Load citrix page and file is automatically downloaded.
- before doing anything else, check if there was a success request and successful download. 
- if there was, open the file
- if there wasn't or those requests did get sent then move to scenario 2

## Scenario 2: Load citrix page, file not downloaded, open "citrix machine" 
- When the open button is clicked, a request is sent out to: 
    <citrix-url>/Citrix/AppStoreWeb/Resources/GetLaunchStatus/<ica-file-name-id> \
    --data-raw 'displayNameDesktopTitle=<desktop-name>&createFileFetchTicket=false'

    Response: {"fileFetchUrl":null,"pollTimeout":5,"status":"retry"}

    The browser tries this several times until the Response is: 
    {"fileFetchUrl":null,"status":"success"}

    Then the browser runs: 
    <citrix-url>/Citrix/AppStoreWeb/Resources/LaunchIca/<ica-file-name-id>.ica?CsrfToken=<token>&IsUsingHttps=Yes&displayNameDesktopTitle=<desktop-name>&launchId=<launch-id>

    This downloads the ica file to the browser folder. 

    I wonder if the approach, instead of refreshing the page is to just monitor the request that the browser is making. To check that it is still trying to get a success true. 

## Scenario 3: Load citrix page, file not downloaded, open results in several retries til a "Cannot start dialog"
- After the open button is clicked and requests are sent to check status. The request to: 
    <citrix-url>/Citrix/AppStoreWeb/Resources/GetLaunchStatus/<ica-file-name-id> \
    --data-raw 'displayNameDesktopTitle=<desktop-name>&createFileFetchTicket=false

    Response: {"errorId":"UnavailableDesktop","fileFetchUrl":null,"status":"failure"}

    Popup in the Browser is: "Cannot start desktop "Name of desktop"" with an OK button. 

- There are two options from here attempt open again (Scenario 2) or Restart

# Scenario 4: Load citrix page, file not downloaded, open results in several retries til a "Cannot start dialog". Attempt Restart
- need to document this