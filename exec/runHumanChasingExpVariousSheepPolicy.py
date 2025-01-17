import os
import pickle
import sys

sys.path.append(os.path.join(os.path.join(os.path.dirname(__file__), '..')))
import collections as co
import itertools as it
import functools as ft

import numpy as np
import random
import pygame as pg
from pygame.color import THECOLORS
from src.visualization import DrawBackground, DrawImage, GiveExperimentFeedback, InitializeScreen, \
    DrawAttributionTrail, DrawImageWithJoysticksCheck, DrawNewStateWithBlocksAndFeedback
from src.controller import HumanController, ModelController, JoyStickForceControllers
from src.writer import WriteDataFrameToCSV
from src.trial import NewtonChaseTrialAllCondtionVariouSpeed, isAnyKilled, CheckTerminationOfTrial, RecordEatenNumber
from src.experiment import NewtonExperiment
from src.maddpg.trainer.myMADDPG import ActOneStep, BuildMADDPGModels, actByPolicyTrainNoisy
from src.functionTools.loadSaveModel import saveToPickle, restoreVariables, GetSavePath
from env.multiAgentEnv import StayInBoundaryByReflectVelocity, TransitMultiAgentChasingForExpWithNoise, GetCollisionForce,\
    ApplyActionForce, ApplyEnvironForce, getPosFromAgentState, getVelFromAgentState, getCaughtHistoryFromAgentState,\
    ObserveWithCaughtHistory, ReshapeActionVariousForce, ResetMultiAgentNewtonChasingVariousSheepWithCaughtHistory, \
    ResetStateWithCaughtHistory, CalSheepCaughtHistory, IntegrateStateWithCaughtHistory, RewardWolfWithBiteAndKill, \
    IsCollision, BuildGaussianFixCov, sampleFromContinuousSpace
from collections import OrderedDict


def main():
    dirName = os.path.dirname(__file__)

    wolfActionUpdateInterval = 1
    sheepActionUpdateInterval = 1
    manipulatedVariables = OrderedDict()
    manipulatedVariables['sheepNums'] = [1, 2]
    manipulatedVariables['sheepWolfForceRatio'] = [1.0]
    manipulatedVariables['sheepConcern'] = ['all']
    # manipulatedVariables['sheepConcern'] = ['self', 'all']
    trailNumEachCondition = 1

    productedValues = it.product(*[[(key, value) for value in values] for key, values in manipulatedVariables.items()])
    parametersAllCondtion = [dict(list(specificValueParameter)) for specificValueParameter in productedValues]
    AllConditions = parametersAllCondtion * trailNumEachCondition
    # random.shuffle(AllConditions)

    experimentValues = co.OrderedDict()
    experimentValues["name"] = input("Please enter players' name:").capitalize()

    mapSize = 1.0
    displaySize = 1.0
    minDistance = mapSize * 1 / 3
    wolfSize = 0.065
    sheepSize = 0.065
    blockSize = 0.13

    screenWidth = int(800)
    screenHeight = int(800)
    fullScreen = False
    initializeScreen = InitializeScreen(screenWidth, screenHeight, fullScreen)
    screen = initializeScreen()

    backgroundColor = THECOLORS['grey']  # [205, 255, 204]
    # targetColor = [THECOLORS['orange'], THECOLORS['chocolate1'], THECOLORS['tan1'], THECOLORS[
    #     'goldenrod2']]  # 'orange', (255, 165, 0); 'chocolate1', (255, 127, 36); 'tan1', (255, 165, 79); 'goldenrod1', (255, 193, 37)
    targetColor = [THECOLORS['orange']] * 16  # [255, 50, 50]
    playerColors = [THECOLORS['red3'], THECOLORS['blue3'],
                    THECOLORS['green4']]  # 'red3', (205, 0, 0); 'blue3', (0, 0, 205); 'green4', (0, 139, 0)
    blockColors = [THECOLORS['white']] * 2
    textColorTuple = THECOLORS['green']

    gridSize = 40
    leaveEdgeSpace = 5
    playerRadius = int(wolfSize / (displaySize * 2) * screenWidth * gridSize / (gridSize + 2 * leaveEdgeSpace))
    targetRadius = int(sheepSize / (displaySize * 2) * screenWidth * gridSize / (gridSize + 2 * leaveEdgeSpace))
    blockRadius = int(blockSize / (displaySize * 2) * screenWidth * gridSize / (gridSize + 2 * leaveEdgeSpace))
    stopwatchUnit = 100
    finishTime = 1000 * 30
    stopwatchEvent = pg.USEREVENT + 1

    pg.time.set_timer(stopwatchEvent, stopwatchUnit)
    pg.event.set_allowed([pg.KEYDOWN, pg.QUIT, stopwatchEvent])
    pg.key.set_repeat(120, 120)
    picturePath = os.path.abspath(os.path.join(os.path.join(dirName, '..'), 'pictures'))
    resultsDicPath = os.path.join(dirName, '..', 'results')

    # experimentValues["name"] = '0704'
    writerPath = os.path.join(resultsDicPath, experimentValues["name"]) + '.csv'
    picklePath = os.path.join(resultsDicPath, experimentValues["name"]) + '.pickle'
    writer = WriteDataFrameToCSV(writerPath)
    pickleWriter = lambda data: saveToPickle(data, picklePath)
    introductionImage = pg.image.load(os.path.join(picturePath, 'introduction-waitall.png'))
    restImage = pg.image.load(os.path.join(picturePath, 'rest-waitall.png'))
    finishImage = pg.image.load(os.path.join(picturePath, 'finish.png'))
    introductionImage = pg.transform.scale(introductionImage, (screenWidth, screenHeight))

    # --------environment setting-----------
    numWolves = 3
    experimentValues["numWolves"] = numWolves
    numBlocks = 2
    sheepLife = 3
    allSheepPolicy = {}
    allWolfRewardFun = {}
    allTransitFun = {}
    for numSheeps in manipulatedVariables['sheepNums']:
        for sheepConcern in manipulatedVariables['sheepConcern']:
            numAgents = numWolves + numSheeps
            numEntities = numAgents + numBlocks
            wolvesID = list(range(numWolves))
            sheepsID = list(range(numWolves, numAgents))
            blocksID = list(range(numAgents, numEntities))

            entitiesSizeList = [wolfSize] * numWolves + [sheepSize] * numSheeps + [blockSize] * numBlocks

            wolfMaxSpeed = 1.0
            sheepMaxSpeed = 1.0
            blockMaxSpeed = None

            entityMaxSpeedList = [wolfMaxSpeed] * numWolves + [sheepMaxSpeed] * numSheeps + [blockMaxSpeed] * numBlocks
            entitiesMovableList = [True] * numAgents + [False] * numBlocks
            massList = [1.0] * numEntities
            reset = ResetMultiAgentNewtonChasingVariousSheepWithCaughtHistory(numWolves, numBlocks, mapSize, minDistance)
            isCollision = IsCollision(getPosFromAgentState)
            rewardWolf = RewardWolfWithBiteAndKill(wolvesID, sheepsID, entitiesSizeList, isCollision, getCaughtHistoryFromAgentState, sheepLife)
            allWolfRewardFun.update({(numSheeps, sheepConcern): rewardWolf})

            stayInBoundaryByReflectVelocity = StayInBoundaryByReflectVelocity([-displaySize, displaySize], [-displaySize, displaySize])

            def checkBoudary(agentState):
                newState = stayInBoundaryByReflectVelocity(getPosFromAgentState(agentState), getVelFromAgentState(agentState))
                return newState

            def checkBoudaryWithCaughtHistory(agentState):
                position = getPosFromAgentState(agentState)
                velocity = getVelFromAgentState(agentState)
                adjustedState = stayInBoundaryByReflectVelocity(position, velocity)
                if len(agentState) == 5:
                    adjustedState = np.append(adjustedState, getCaughtHistoryFromAgentState(agentState))
                return adjustedState.copy()

            # checkAllAgents = lambda states: [checkBoudary(agentState) for agentState in states]
            checkAllAgents = lambda states: [checkBoudaryWithCaughtHistory(agentState) for agentState in states]
            # reshapeHumanAction = ReshapeHumanAction()
            # reshapeSheepAction = ReshapeSheepAction()
            reShapeAction = ReshapeActionVariousForce()
            getCollisionForce = GetCollisionForce()
            applyActionForce = ApplyActionForce(wolvesID, sheepsID, entitiesMovableList)
            applyEnvironForce = ApplyEnvironForce(numEntities, entitiesMovableList, entitiesSizeList, getCollisionForce,
                                                  getPosFromAgentState)
            calSheepCaughtHistory = CalSheepCaughtHistory(wolvesID, numBlocks, entitiesSizeList, isCollision, sheepLife)
            integrateState = IntegrateStateWithCaughtHistory(numEntities, entitiesMovableList, massList, entityMaxSpeedList,
                                            getVelFromAgentState, getPosFromAgentState, calSheepCaughtHistory, damping=0.25, dt=0.05)

            actionDimReshaped = 2
            cov = [0.3 ** 2 for _ in range(actionDimReshaped)]
            buildGaussian = BuildGaussianFixCov(cov)
            noiseAction = lambda state: sampleFromContinuousSpace(buildGaussian(tuple(state)))
            transit = TransitMultiAgentChasingForExpWithNoise(reShapeAction, reShapeAction, applyActionForce,
                                                              applyEnvironForce, integrateState, checkAllAgents,
                                                              noiseAction)
            allTransitFun.update({(numSheeps, sheepConcern): transit})

            # transit = TransitMultiAgentChasingForExpVariousForce(reShapeAction, reShapeAction, applyActionForce, applyEnvironForce, integrateState, checkAllAgents)

            def loadPolicyOneCondition(numSheeps, sheepConcern):
                # -----------observe--------
                if sheepConcern == 'self':
                    numSheepToObserve = 1
                if sheepConcern == 'all':
                    numSheepToObserve = numSheeps

                wolvesIDForSheepObserve = list(range(numWolves))
                sheepsIDForSheepObserve = list(range(numWolves, numSheepToObserve + numWolves))
                blocksIDForSheepObserve = list(
                    range(numSheeps + numWolves, numSheeps + numWolves + numBlocks))
                observeOneAgentForSheep1 = lambda agentID, sId: ObserveWithCaughtHistory(agentID, wolvesIDForSheepObserve, sId,
                                                                                         blocksIDForSheepObserve, getPosFromAgentState,
                                                                                         getVelFromAgentState, getCaughtHistoryFromAgentState)
                observeOneAgentForSheep = ft.partial(observeOneAgentForSheep1, sId=sheepsIDForSheepObserve)
                observeOneForSheep = lambda state, num: [observeOneAgentForSheep(agentID)(state) for agentID in
                                                         range(num)]
                sheepObserve = ft.partial(observeOneForSheep, num=numWolves + numSheepToObserve)
                sheepObsList = []
                for sheepId in sheepsID:
                    obsFunList = [ObserveWithCaughtHistory(agentID, wolvesIDForSheepObserve, [sheepId], blocksIDForSheepObserve,
                                          getPosFromAgentState, getVelFromAgentState, getCaughtHistoryFromAgentState)
                                  for agentID in list(range(numWolves)) + [sheepId]]
                    sheepObsLambda = lambda state, obsList: list([obs(state) for obs in obsList])
                    sheepObs = ft.partial(sheepObsLambda, obsList=obsFunList)
                    sheepObsList.append(sheepObs)
                initSheepObsForParams = sheepObserve(reset(numSheeps))
                obsSheepShape = [initSheepObsForParams[obsID].shape[0] for obsID in range(len(initSheepObsForParams))]

                worldDim = 2
                actionDim = worldDim * 2 + 1
                layerWidth = [128, 128]

                # -----------model--------
                # modelFolderName = 'withoutWall3wolves'
                # modelFolderName = 'withoutWall2wolves'
                modelFolderName = 'newRewardIndividualAllSheep2block12Wepisode'

                maxEpisode = 120000
                evaluateEpisode = 120000
                maxTimeStep = 75
                modelSheepSpeed = 1.0

                buildSheepMADDPGModels = BuildMADDPGModels(actionDim, numWolves + numSheepToObserve, obsSheepShape)
                sheepModelsListAll = [buildSheepMADDPGModels(layerWidth, agentID) for agentID in
                                      range(numWolves, numWolves + numSheepToObserve)]
                sheepModelsListSep = [buildSheepMADDPGModels(layerWidth, agentID) for agentID in
                                      range(numWolves, numWolves + numSheepToObserve) for i in range(numSheeps)]

                modelFolder = os.path.join(dirName, '..', 'model', modelFolderName)
                sheepFileNameSep = "maddpg{}wolves1sheep{}blocks{}episodes{}stepSheepSpeed{}shared_agent3".format(
                    numWolves, numBlocks, maxEpisode, maxTimeStep, modelSheepSpeed)
                # sheepFileNameAll = "maddpg{}wolves{}sheep{}blocks{}episodes{}stepSheepSpeed{}WolfActCost0.0individ1.0_agent".format(numWolves, numSheepToObserve, numBlocks, maxEpisode, maxTimeStep, modelSheepSpeed)
                # sheepFileNameAll = "maddpg{}wolves{}sheep{}blocks{}episodes{}stepSheepSpeed{}shared_agent".format(
                #     numWolves, numSheepToObserve, numBlocks, maxEpisode, maxTimeStep, modelSheepSpeed)
                sheepFileNameAll = "maddpg{}wolves{}sheep{}blocks{}episodes{}stepSheepSpeed{}individ_agent".format(
                    numWolves, numSheepToObserve, numBlocks, maxEpisode, maxTimeStep, modelSheepSpeed)
                sheepModelPathsAll = [
                    os.path.join(modelFolder, sheepFileNameAll + str(i) + str(evaluateEpisode) + 'eps') for i in
                    range(numWolves, numWolves + numSheepToObserve)]
                sheepModelPathsSep = [
                    os.path.join(modelFolder, 'trainingId' + str(i) + sheepFileNameSep + str(evaluateEpisode) + 'eps')
                    for i in range(numSheeps)]

                actOneStepOneModel = ActOneStep(actByPolicyTrainNoisy)

                if sheepConcern == 'self':
                    [restoreVariables(model, path) for model, path in zip(sheepModelsListSep, sheepModelPathsSep)]
                    sheepPolicyFun = lambda allAgentsStates: list([actOneStepOneModel(model, sheepObsList[i](allAgentsStates)) for i, model in enumerate(sheepModelsListSep)])
                    sheepPolicyOneCondition = sheepPolicyFun
                else:
                    [restoreVariables(model, path) for model, path in zip(sheepModelsListAll, sheepModelPathsAll)]
                    sheepPolicyFun = lambda allAgentsStates, obs: [actOneStepOneModel(model, obs(allAgentsStates)) for model in sheepModelsListAll]
                    sheepPolicyOneCondition = ft.partial(sheepPolicyFun, obs=sheepObserve)
                return sheepPolicyOneCondition

            sheepPolicy = loadPolicyOneCondition(numSheeps, sheepConcern)
            allSheepPolicy.update({(numSheeps, sheepConcern): sheepPolicy})

    checkTerminationOfTrial = CheckTerminationOfTrial(finishTime)
    killzone = wolfSize + sheepSize
    recordEaten = RecordEatenNumber(isAnyKilled)
    humanController = JoyStickForceControllers()
    getEntityPos = lambda state, entityID: getPosFromAgentState(state[entityID])
    getEntityVel = lambda state, entityID: getVelFromAgentState(state[entityID])
    getEntityCaughtHistory = lambda state, entityID: getCaughtHistoryFromAgentState(state[entityID])

    drawImage = DrawImage(screen)
    drawImageBoth = DrawImageWithJoysticksCheck(screen, humanController.joystickList)
    drawBackground = DrawBackground(screen, gridSize, leaveEdgeSpace, backgroundColor, textColorTuple, playerColors)
    drawNewState = DrawNewStateWithBlocksAndFeedback(screen, drawBackground, playerColors, blockColors, targetRadius,
                                                     playerRadius, blockRadius, displaySize, sheepLife)
    trial = NewtonChaseTrialAllCondtionVariouSpeed(screen, killzone, targetColor, numWolves, numBlocks, stopwatchEvent,
                                                   drawNewState, checkTerminationOfTrial, recordEaten, humanController,
                                                   getEntityPos, getEntityVel, getEntityCaughtHistory,
                                                   allSheepPolicy, allTransitFun, allWolfRewardFun,
                                                   wolfActionUpdateInterval, sheepActionUpdateInterval)
    print('aaa')
    hasRest = False
    # resetWithCaughtHistory = ResetStateWithCaughtHistory(reset, calSheepCaughtHistory)

    experiment = NewtonExperiment(restImage, hasRest, trial, writer, pickleWriter, experimentValues, reset,
                                  drawImageBoth)
    # giveExperimentFeedback = GiveExperimentFeedback(screen, textColorTuple, screenWidth, screenHeight)
    drawImageBoth(introductionImage)
    block = 1
    restTimes = 3  # the number of breaks in an experiment
    for i in range(block):
        experiment(finishTime, AllConditions, restTimes)
        # giveExperimentFeedback(i, score)
        if i == block - 1:
            drawImage(finishImage)
        else:
            drawImageBoth(restImage)


if __name__ == "__main__":
    main()
