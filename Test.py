from Utils import TrainingSessionUtils


trainingYear = TrainingSessionUtils.makeSessions("templates/exampleLog.md")
#TrainingSessionUtils.getSplits(trainingYear)
#TrainingSessionUtils.visulizeVolumeByWeek(trainingYear)
#TrainingSessionUtils.visualizeDistanceByTime(trainingYear, 17)
#TrainingSessionUtils.visualizePersonalBests()
#print(TrainingSessionUtils.analyzeTextPerplex(trainingYear))

TrainingSessionUtils.analyzeTextHG(trainingYear)

