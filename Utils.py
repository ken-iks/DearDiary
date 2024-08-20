import matplotlib.pyplot as plt
from datetime import timedelta, date
import re
import time
import os
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import Query
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from transformers import pipeline
from keybert import KeyBERT


class TrainingSession:

    def createDate(self, topLine):
        if not TrainingSession.isMeet(topLine):
            stringDate1 = topLine.split("-")[0].strip()
            stringDate2 = stringDate1.split(" ")[1].strip()
            stringDate3 = stringDate2.split("/")
            month = int(stringDate3[0])
            day = int(stringDate3[1])
            if (month > 8):
                return date(2023, month, day)
            else:
                return date(2024, month, day)
        else:
            # Regular expression to find the date (format: MM/DD)
            date_pattern = re.compile(r'\b\d{2}/\d{2}\b')
            # Search for the patterns in the line
            date_match = date_pattern.search(topLine)
            # Extract the matches
            stringDate = date_match.group()
            stringDate1 = stringDate.split("/")
            month = int(stringDate1[0])
            day = int(stringDate1[1])
            if (month > 8):
                return date(2023, month, day)
            else:
                return date(2024, month, day)

    # QUICK WORKAROUND - NEED BETTER FIX
    def isMeet(topline):
        return topline[:4].lower() == "meet"
    
    def isMeet2(self, topline):
        return topline[:4].lower() == "meet"
    
    # returns string array of session, with each entry of form 'WxR D'
    def serializeSesh(input_string):
        # Updated pattern to match AxB (with or without space between A and xB), optional distance D (with or without 'ish' or '+'), and handle special cases
        pattern = r'(\d+(?:\.\d+)?(?:lbs|kg|k)?(?:\s+1wind)?(?:\s+\d+t)?(?:\s*(?:k)?(?:3/4|1/2))?\s*x\d+)\s*(\d+(?:\.\d+)?(?:m)?(?:\+|ish)?)?'
        # Find all matches in the input string
        matches = re.findall(pattern, input_string)

        result = []
        for match in matches:
            weight_rep = match[0]
            distance = match[1] if match[1] else '0'
            # Handle the special cases for weights
            weight_rep = re.sub(r'(\d+)(k|kg)? 3/4', r'\1.75k', weight_rep)
            weight_rep = re.sub(r'(\d+)(k|kg)? 1/2', r'\1.5k', weight_rep)
            weight_rep = re.sub(r'(\d+) 1/2', r'\1.5k', weight_rep)
            # Remove 'ish' and '+' from distance
            distance = re.sub(r'ish|\+', '', distance)
            weight_rep = re.sub(r'5t', '', weight_rep)
            weight_rep = re.sub(r'1wind', '', weight_rep)
            # Construct the final string for the weight and distance
            result.append(f"{weight_rep.strip()} {distance.strip()}")

        return result
    
    def convertLBS(stringWeight):
        KG_TO_LBS = 2.20462
        # Regular expression to extract the weight and unit
        match = re.match(r'(\d+(?:\.\d+)?)(kg|k|lbs)?', stringWeight)
        if not match:
            return None  # or raise an error if the input format is not as expected

        weight = float(match.group(1))
        unit = match.group(2)

        if unit == "kg" or unit == "k" or unit is None:
            return round(weight * KG_TO_LBS)
        else:
            return round(weight)
    
    def getBreakdown(self, topline):
        if TrainingSession.isMeet(topline):
            # Regular expression to find the distance (a number followed by 'm')
            distance_pattern = re.compile(r'\b\d+\.\d{2}(?=m\b)')
            distance_match = distance_pattern.search(topline)
            distance = distance_match.group()
            floatDistance = float(distance[:-1])
            if floatDistance < 50.0:
                return [35], {35:6}, {35:floatDistance}
            else:
                return [16], {16:6}, {16:floatDistance}

        else:
            balls = []
            reps = {}
            distances = {}
            stringSeshes = TrainingSession.serializeSesh(topline)
            for sesh in stringSeshes:
                w_r_d = sesh.split(" ")
                w_r_d = [i for i in w_r_d if i != '']
                # Edge case: xN is within first element
                if len(w_r_d) == 2:
                    pointer = w_r_d[0].find('x')
                    w_r_d = [w_r_d[0][:pointer], w_r_d[0][pointer:], w_r_d[1]]
                ballWeight = TrainingSession.convertLBS(w_r_d[0])
                repNumber = int(w_r_d[1][1:])
                distanceNumber = float(w_r_d[2].replace('m',''))
                balls.append(ballWeight)
                reps[ballWeight] = repNumber
                distances[ballWeight] = distanceNumber
    
            return balls, reps, distances
        
    def filterAnomalies(self):
        if self.meet:
            return
        for weight, distance in self.distances.items():
            personal_best = TrainingSessionUtils.getPB(weight)
            if personal_best and distance < (personal_best * 0.85):  # Example threshold
                self.distances[weight] = 0  # Setting the distance to zero as if it wasn't measured
            else:
                # Update the personal best if the current distance is better
                TrainingSessionUtils.updatePB(weight, distance)

    def to_dict(self):
        return {
            'summary': self.summary,
            'date': self.date.isoformat(),  # assuming `self.date` is a `datetime.date` object
            'balls': self.balls,
            'reps': self.reps,
            'distances': self.distances,
            'meet': self.meet,
            # Add other attributes if needed
        }
    
    @classmethod
    def from_dict(cls, data):
        instance = cls.__new__(cls)  # bypasses __init__
        instance.summary = data['summary']
        instance.date = date.fromisoformat(data['date'])  # Convert back to date object
        instance.balls = data['balls']
        instance.reps = data['reps']
        instance.distances = {int(k): v for k, v in data['distances'].items()}
        instance.meet = data['meet']
        # Assign other attributes as needed
        return instance

    def __init__(self, rawData):
        self.summary = rawData.split("\n", 1) #index 0 is top line, index 1 is description
        self.date = self.createDate(self.summary[0])
        self.meet = self.isMeet2(self.summary[0])
        self.balls, self.reps, self.distances = self.getBreakdown(self.summary[0])
        self.filterAnomalies()

class TrainingSessionUtils:
    personalBests = {}

    @staticmethod
    def updatePB(weight, distance):
        if weight not in TrainingSessionUtils.personalBests:
            TrainingSessionUtils.personalBests[weight] = distance
        else:
            if distance > TrainingSessionUtils.personalBests[weight]:
                TrainingSessionUtils.personalBests[weight] = distance
    
    @staticmethod
    def getPB(weight):
        return TrainingSessionUtils.personalBests.get(weight, None)

    @staticmethod
    def getSplits(sessionList):
        heavy, standard, light = 0, 0, 0
        for sesh in sessionList:
            for ball in sesh.balls:
                if ball > 16:
                    heavy+=sesh.reps[ball]
                elif ball < 16:
                    light+=sesh.reps[ball]
                else:
                    standard+=sesh.reps[ball]
        heavy_perc = (heavy / (heavy + standard + light) ) * 100
        light_perc = (light / (heavy + standard + light) ) * 100
        standard_perc = (standard / (heavy + standard + light) ) * 100

        print("HEAVY PERCENTAGE: " + str(round(heavy_perc,3)) + "%")
        print("LIGHT PERCENTAGE: " + str(round(light_perc,3)) + "%")
        print("STANDARD PERCENTAGE: " + str(round(standard_perc,3)) + "%")

    # main_split is the main splitting algorithm that splits the training log into
    # the string that will make up each training log instance. Should be left with
    # an array of strings that is basically the summary of each training session
    @staticmethod
    def mainSplit(name): 
        # Read the text file into a string
        with open(name, 'r') as file:
            content = file.read()
        # Split the string by one or more empty lines
        sections = re.split(r'\n\s*\n+', content)
        return sections

    # transform a string session list to a list of training session objects
    @staticmethod
    def makeSessions(name):
        stringSessions = TrainingSessionUtils.mainSplit(name)
        retArray = []
        for session in stringSessions[1:]:
            #print(session)
            sesh = TrainingSession(session) #assume that constructor creates desired object
            retArray.append(sesh)
        return retArray

    @staticmethod
    #check function for main_split
    def checkSplit(array):
        # Print the result
        for i, section in enumerate(array):
            print(f"Section {i+1}:")
            print(section)
            print('-' * 40)  

    # --------------- VISUALIZATION 1 ------------------------------

    @staticmethod
    def calcVolumeByWeek(sessionList):
        weekly_volume = {}
        meet_dates = []
        for sesh in sessionList:
            # Calculate the start of the week (Monday) for the session's date
            week_start = sesh.date - timedelta(days=sesh.date.weekday())
            if week_start not in weekly_volume:
                weekly_volume[week_start] = 0
            # Add the total reps for the session to the corresponding week
            weekly_volume[week_start] += sum(sesh.reps.values())
            if sesh.meet:  # Check if this session is a meet
                meet_dates.append(sesh.date)
        return weekly_volume, meet_dates
    
    @staticmethod
    def plotVolumeByWeek(weekly_volume, meet_dates):
        # Sort weeks by date
        weeks = sorted(weekly_volume.keys())
        volumes = [weekly_volume[week] for week in weeks]

        plt.figure(figsize=(10, 6))
        plt.plot(weeks, volumes, marker='o', label='Weekly Volume')

        # Plot meet dates with red 'X'
        for meet_date in meet_dates:
            plt.plot(meet_date, weekly_volume.get(meet_date - timedelta(days=meet_date.weekday()), 0), 
                     'rx', label='Meet' if meet_date == meet_dates[0] else "")  # label only once
            
        plt.xlabel('Week Starting Date')
        plt.ylabel('Total Reps')
        plt.title('Training Volume Per Week')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Save the plot to a file
        plot_path = os.path.join('static', 'volume_per_week.png')
        plt.savefig(plot_path)
        plt.close()  # Close the figure to free up memory

        return plot_path  # Return the path to the saved image

    @staticmethod
    def visualizeVolumeByWeek(sessionList):
        weekly_volume, meet_dates = TrainingSessionUtils.calcVolumeByWeek(sessionList)
        return TrainingSessionUtils.plotVolumeByWeek(weekly_volume, meet_dates)
    
    # --------------- VISULIZATION 2 ------------------------------

    @staticmethod
    def calcDistanceByTime(sessionList, weight):
        distance_over_time = {}
        meet_dates = {}

        for sesh in sessionList:
            if sesh.meet:
                if sesh.date < date(2024, 3, 28):
                    #distance = sesh.distances[35] - ignore weight throw
                    pass
                else:
                    distance = sesh.distances[16]
                    meet_dates[sesh.date] = distance
            elif weight in sesh.balls :
                distance = sesh.distances[weight]
                if distance > 0:  # Ignore cases where distance is 0
                    distance_over_time[sesh.date] = distance


        return distance_over_time, meet_dates

    @staticmethod
    def plotDistanceByTime(distance_over_time, meet_dates, weight):
        dates = sorted(distance_over_time.keys())
        distances = [distance_over_time[date] for date in dates]

        plt.figure(figsize=(10, 6))
        plt.plot(dates, distances, marker='o', label=f'{weight}lbs Distance Over Time')
        
        # Mark the meet dates with red X's
        if meet_dates:
            meet_dates_filtered = sorted(meet_dates.keys())
            meet_distances = [meet_dates[date] for date in meet_dates_filtered]
            plt.scatter(meet_dates_filtered, meet_distances, color='red', marker='x', s=100, label='Meet (16lbs) Distance')

        plt.xlabel('Date')
        plt.ylabel('Distance (m)')
        plt.title(f'Training Distance Over Time for {weight}lbs')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Save the plot to a file
        plot_path = os.path.join('static', 'distance_over_time.png')
        plt.savefig(plot_path)
        plt.close()  # Close the figure to free up memory

        return plot_path  # Return the path to the saved image

    @staticmethod
    def visualizeDistanceByTime(sessionList, weight):
        distance_over_time, meet_dates = TrainingSessionUtils.calcDistanceByTime(sessionList, weight)
        return TrainingSessionUtils.plotDistanceByTime(distance_over_time, meet_dates, weight)

    # --------------- VISULIZATION 3 ------------------------------

    @staticmethod
    def visualizePersonalBests():
        if not TrainingSessionUtils.personalBests:
            print("No personal bests to display.")
            return
        personalBests = TrainingSessionUtils.personalBests
        filteredBests = {weight:dist for weight,dist in personalBests.items()
                         if 10 <= weight <= 22}
        # Extract weights and corresponding personal best distances
        weights = list(filteredBests.keys())
        distances = list(filteredBests.values())

        if not filteredBests:
            print("No personal bests in the specified weight range (10lbs - 22lbs).")
            return

        # Create the bar chart
        plt.figure(figsize=(10, 6))
        bars = plt.bar(weights, distances, color='blue')

        # Add text labels on top of each bar
        for bar, distance in zip(bars, distances):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() - 0.1, 
                     f'{distance:.2f}m', ha='center', va='bottom', color='black', fontsize=10, fontweight='bold')

        # Add title and labels
        plt.title('Personal Best Distances for Each Weight')
        plt.xlabel('Weight (lbs)')
        plt.ylabel('Distance (m)')
        plt.xticks(weights)

        # Show the plot
        plt.tight_layout()
        plt.show()

        # Save the plot to file
        plot_path = os.path.join('static', 'personal_bests.png')
        plt.savefig(plot_path)
        plt.close()  # Close the figure to free up memory

        return plot_path  # Return the path to the saved image

    # --------------- ANALYSIS 1 ------------------------------
    def analyzeTextPerplex(sessionList):
        # Set up Chrome options to run in headless mode
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Runs Chrome in headless mode.
        chrome_options.add_argument("--disable-gpu")  # Disables GPU hardware acceleration. It's recommended to use this option.
        chrome_options.add_argument("--window-size=1920,1080")  # Optional: Set a specific window size.
        chrome_options.add_argument("--disable-extensions")  # Disables extensions.
        chrome_options.add_argument("--no-sandbox")  # Bypass OS security model.
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems.

        # Initialize the Chrome WebDriver
        driver = webdriver.Chrome(service=Service(), options=chrome_options)

        # Open the Perplexity AI website
        driver.get("https://www.perplexity.ai/")

        # Wait for the page to load
        time.sleep(1)

        resultsList = []
        # Process the session list in chunks of 25
        # TODO: THIS IS FUNCTION BUT VERYYYY SLOW
        for i in range(0, len(sessionList), 25):
            summaryList = [f"Session {idx + 1}: {session.summary[1]}" for idx, session in enumerate(sessionList[i:i + 25])]
            summaryString = ", ".join(summaryList)
            try:
                queryString = f"You are a hammer throwing coach/assistant who is analyzing the training logs of an \
                elite level hammer thrower who is trying to make technical progress by focusing on a smaller number of \
                technical cues (max 5) over the course of the next season in order to improve the consistancy and also improve their \
                personal best to reach 80 metres (current personal best is 77.92). Use your knowledge of hammer throwing and also \
                analyze the following training summaries in order to provide insights on the technical cues the thrower needs \
                to focus on to improve their results: {summaryString}"
                result = Query.analyzeText(queryString, driver)
                # Retry incase of cache issues
                while not result:
                    result = Query.analyzeText(queryString, driver)

                resultsList.append(result)

            except Exception as e:
                driver.quit()
                return f"An error occurred in analyzeText: {str(e)}"
            
        driver.quit()

        # Combine all results into a final query for a comprehensive analysis
        final_summary = "\n".join(resultsList)

        # Initialize the Chrome WebDriver again for the final query
        driver = webdriver.Chrome(service=Service(), options=chrome_options)
        driver.get("https://www.perplexity.ai/")
        time.sleep(1)

        try:
            final_query = f"Based on the following analysis of the hammer thrower's training summaries over the season, \
            please provide a final list of 5 key technical cues that the thrower should focus on to achieve their goal \
            of reaching 80 metres: {final_summary}"
            
            final_result = Query.analyzeText(final_query, driver)
            while not final_result:
                final_result = Query.analyzeText(final_query, driver)
            
            driver.quit()
            return final_result

        except Exception as e:
            driver.quit()
            return f"An error occurred in the final analysis: {str(e)}"
        
    # --------------- ANALYSIS 2 ------------------------------    
    def analyzeTextHG(sessionList):
        # Load pre-trained models for sentiment analysis and feature extraction
        sentiment_analyzer = pipeline("sentiment-analysis")
        kw_model = KeyBERT()

        summaryList = [f"Session {idx + 1}: {Query.clean_text(i.summary[1])}" 
                       for idx, i in enumerate(sessionList)]
        
        positiveSessions = []

        for session in summaryList:
            sentiment = sentiment_analyzer(session)
            if sentiment[0]['label'] == 'POSITIVE':
                positiveSessions.append(session)
        
        # Step 2: Aggregate all positive sessions into a single text
        aggregated_text = " ".join(positiveSessions)

        # Step 3: Extract keywords/phrases from the aggregated text
        keywords = kw_model.extract_keywords(aggregated_text, keyphrase_ngram_range=(1, 2), stop_words='english')

        # Display the results
        print("Aggregated Keywords/Phrases from Positive Sessions:")
        for keyword in keywords:
            print(keyword)

