import numpy as np
import scipy.stats as ss

getPosFromAgentState = lambda state: np.array([state[0], state[1]])
getVelFromAgentState = lambda state: np.array([state[2], state[3]])
getCaughtHistoryFromAgentState = lambda state: np.array(state[4])


class StayInBoundaryByReflectVelocity():
    def __init__(self, xBoundary, yBoundary):
        self.xMin, self.xMax = xBoundary
        self.yMin, self.yMax = yBoundary

    def __call__(self, position, velocity):
        adjustedX, adjustedY = position
        # if adjustedX > 1 or adjustedY > 1:
        #     print("out of boundary!!!")
        #     print("position",position)
        #     print(self.xMin)
        adjustedVelX, adjustedVelY = velocity
        if position[0] >= self.xMax:
            adjustedX = 2 * self.xMax - position[0]
            adjustedVelX = -abs(velocity[0])
        if position[0] <= self.xMin:
            adjustedX = 2 * self.xMin - position[0]
            adjustedVelX = abs(velocity[0])
        if position[1] >= self.yMax:
            adjustedY = 2 * self.yMax - position[1]
            adjustedVelY = -abs(velocity[1])
        if position[1] <= self.yMin:
            adjustedY = 2 * self.yMin - position[1]
            adjustedVelY = abs(velocity[1])
        checkedPosition = np.array([adjustedX, adjustedY])
        checkedVelocity = np.array([adjustedVelX, adjustedVelY])
        return np.array(list(checkedPosition) + list(checkedVelocity))


class GetActionCost:
    def __init__(self, costActionRatio, reshapeAction, individualCost):
        self.costActionRatio = costActionRatio
        self.individualCost = individualCost
        self.reshapeAction =reshapeAction

    def __call__(self, agentsActions):
        agentsActions = [self.reshapeAction(action) for action in agentsActions]
        actionMagnitude = [np.linalg.norm(np.array(action), ord=2) for action in agentsActions]
        cost = self.costActionRatio * np.array(actionMagnitude)
        numAgents = len(agentsActions)
        groupCost = cost if self.individualCost else [np.sum(cost)] * numAgents

        return groupCost


class IsCollision:
    def __init__(self, getPosFromState, killZoneRatio = 1.0):
        self.getPosFromState = getPosFromState
        self.killZoneRatio = killZoneRatio

    def __call__(self, agent1State, agent2State, agent1Size, agent2Size):
        posDiff = self.getPosFromState(agent1State) - self.getPosFromState(agent2State)
        dist = np.sqrt(np.sum(np.square(posDiff)))
        minDist = (agent1Size + agent2Size) * self.killZoneRatio
        return True if dist < minDist else False


class RewardWolf:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, isCollision, collisionReward, individual):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.collisionReward = collisionReward
        self.individual = float(
            individual)  # self.individual = 0.8: 0.8* reward give myself, 0.2* reward split to other agents

    def __call__(self, state, action, nextState):
        numWolves = len(self.wolvesID)
        reward = [0] * numWolves

        individualReward = self.individual * self.collisionReward
        sharedRewardForEachAgent = (1 - self.individual) * self.collisionReward / numWolves

        for rewardID, wolfID in enumerate(self.wolvesID):
            wolfSize = self.entitiesSizeList[wolfID]
            wolfNextState = nextState[wolfID]

            for sheepID in self.sheepsID:
                sheepSize = self.entitiesSizeList[sheepID]
                sheepNextState = nextState[sheepID]

                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    reward = [oldReward + sharedRewardForEachAgent for oldReward in reward]
                    reward[rewardID] += individualReward
        return reward


class RewardWolfWithBiteAndKill:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, isCollision, getCaughtHistoryFromAgentState, sheepLife,
                 biteReward=0.1, killReward=1):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.getEntityCaughtHistory = lambda state, entityID: getCaughtHistoryFromAgentState(state[entityID])
        self.sheepLife = sheepLife
        self.biteReward = biteReward
        self.killReward = killReward

    def __call__(self, state, action, nextState):
        wolfReward = 0
        for wolfID in self.wolvesID:
            wolfSize = self.entitiesSizeList[wolfID]
            wolfNextState = nextState[wolfID]
            for sheepID in self.sheepsID:
                sheepSize = self.entitiesSizeList[sheepID]
                sheepNextState = nextState[sheepID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    wolfReward += self.biteReward
                sheepCaughtHistory = self.getEntityCaughtHistory(state, sheepID)
                if sheepCaughtHistory == self.sheepLife:
                    wolfReward += self.killReward
        reward = [wolfReward] * len(self.wolvesID)
        return reward


class ContinuousHuntingRewardWolf:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, isCollision, sheepLife=3, collisionReward=1):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.collisionReward = collisionReward
        self.sheepLife = sheepLife
        # self.sheepsLife = {sheepId:sheepLife for sheepId in sheepsID}
        self.getCaughtHistory = {sheepId:0 for sheepId in sheepsID}
    def __call__(self, state, action, nextState):
        wolfReward = 0
        for sheepID in self.sheepsID:
            sheepSize = self.entitiesSizeList[sheepID]
            sheepNextState = nextState[sheepID]
            getCaught = 0
            for wolfID in self.wolvesID:
                wolfSize = self.entitiesSizeList[wolfID]
                wolfNextState = nextState[wolfID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    self.getCaughtHistory[sheepID] += 1
                    getCaught = 1
                    break
            if not getCaught:
                self.getCaughtHistory[sheepID] = 0
        for sheepID in self.sheepsID:
            if self.getCaughtHistory[sheepID] == self.sheepLife:
                wolfReward += self.collisionReward
                self.getCaughtHistory[sheepID] = 0
        reward = [wolfReward] * len(self.wolvesID)
        return reward


class PunishForOutOfBound:
    def __init__(self):
        self.physicsDim = 2

    def __call__(self, agentPos):
        punishment = 0
        for i in range(self.physicsDim):
            x = abs(agentPos[i])
            punishment += self.bound(x)
        return punishment

    def bound(self, x):
        if x < 0.9:
            return 0
        if x < 1.0:
            return (x - 0.9) * 10
        return min(np.exp(2 * x - 2), 10)


class RewardSheep:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, getPosFromState, isCollision, punishForOutOfBound,
                 collisionPunishment):
        self.wolvesID = wolvesID
        self.getPosFromState = getPosFromState
        self.entitiesSizeList = entitiesSizeList
        self.sheepsID = sheepsID
        self.isCollision = isCollision
        self.collisionPunishment = collisionPunishment
        self.punishForOutOfBound = punishForOutOfBound

    def __call__(self, state, action, nextState):  # state, action not used
        reward = []
        for sheepID in self.sheepsID:
            sheepReward = 0
            sheepNextState = nextState[sheepID]
            sheepNextPos = self.getPosFromState(sheepNextState)
            sheepSize = self.entitiesSizeList[sheepID]

            sheepReward -= self.punishForOutOfBound(sheepNextPos)
            for wolfID in self.wolvesID:
                wolfSize = self.entitiesSizeList[wolfID]
                wolfNextState = nextState[wolfID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    sheepReward -= self.collisionPunishment
            reward.append(sheepReward)
        return reward


class CalSheepCaughtHistory:
    def __init__(self, wolvesID, numBlock, entitiesSizeList, isCollision, sheepLife):
        self.wolvesID = wolvesID
        self.numBlock = numBlock
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.sheepLife = sheepLife
    def __call__(self, state, nextState):
        self.sheepsID = range(len(self.wolvesID), len(state)-self.numBlock)
        self.getCaughtHistory = {sheepId: getCaughtHistoryFromAgentState(state[sheepId]) for sheepId in self.sheepsID}

        for sheepID in self.sheepsID:
            sheepSize = self.entitiesSizeList[sheepID]
            sheepNextState = nextState[sheepID]
            getCaught = 0
            for wolfID in self.wolvesID:
                wolfSize = self.entitiesSizeList[wolfID]
                wolfNextState = nextState[wolfID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    self.getCaughtHistory[sheepID] += 1
                    getCaught = 1
                    break
            if not getCaught:
                self.getCaughtHistory[sheepID] = 0
            if self.getCaughtHistory[sheepID] == self.sheepLife+1:
                self.getCaughtHistory[sheepID] = 0
        return self.getCaughtHistory.copy()

class ResetMultiAgentNewtonChasingVariousSheepWithCaughtHistoryWithDiffBlocks:
    def __init__(self, numWolves, numBlocks, mapSize, minDistance, minDistanceInitBlocks):
        self.positionDimension = 2
        self.numWolves = numWolves
        self.numBlocks = numBlocks
        self.mapSize = mapSize
        self.minDistance = minDistance
        self.minDistanceInitBlocks = minDistanceInitBlocks

    def __call__(self, numSheeps, blockSize):
        if blockSize <= 0:
            self.numBlocks = 0
        else:
            self.numBlocks = 2
        sampleOneAgentPosition = lambda:[round(x,2) for x in
                                         list(np.random.uniform(-self.mapSize, self.mapSize, self.positionDimension))]

        initWolfRandomPos = [sampleOneAgentPosition() for ID in range(self.numWolves)]
        initWolfZeroVel = lambda: np.zeros(self.positionDimension)
        initSheepRandomPos = [sampleOneAgentPosition() for sheepID in range(numSheeps)]
        initSheepRandomVel = lambda: np.random.uniform(0, 1, self.positionDimension)
        initBlockRandomPos = [sampleOneAgentPosition() for blockID in range(self.numBlocks)]
        initBlockZeroVel = lambda: np.zeros(self.positionDimension)

        for i, sheepPos in enumerate(initSheepRandomPos):
            while np.any(np.array([np.linalg.norm(np.array(agentPos) - np.array(sheepPos)) for agentPos in
                                   initWolfRandomPos]) <= self.minDistance):
                sheepPos = sampleOneAgentPosition()
            initSheepRandomPos[i] = sheepPos

        for j, blockPos in enumerate(initBlockRandomPos):
            while (np.any(np.array([np.linalg.norm(np.array(entityPos) - np.array(blockPos)) for entityPos in
                                   initBlockRandomPos]) <= self.minDistanceInitBlocks)
                   or np.any(np.abs(self.mapSize - np.abs(blockPos)) < blockSize)):
                # print('!!!', self.mapSize, self.mapSize - np.abs(blockPos))
                blockPos = sampleOneAgentPosition()
            initBlockRandomPos[j] = blockPos

        agentsState = [state + vel for state, vel in
                       zip(initWolfRandomPos, [list(initWolfZeroVel()) for ID in range(self.numWolves)])]
        sheepState = [state + vel for state, vel in
                      zip(initSheepRandomPos, [list(initSheepRandomVel()) for sheepID in range(numSheeps)])]
        blockState = [state + vel for state, vel in
                      zip(initBlockRandomPos, [list(initBlockZeroVel()) for blockID in range(self.numBlocks)])]
        state = agentsState + sheepState + blockState
        agentInitCaughtHistory = 0
        for agentState in state:
            agentState.append(agentInitCaughtHistory)
        state = np.array(state)

        return state

class ResetMultiAgentNewtonChasingVariousSheepWithCaughtHistory:
    def __init__(self, numWolves, numBlocks, mapSize, minDistance):
        self.positionDimension = 2
        self.numWolves = numWolves
        self.numBlocks = numBlocks
        self.mapSize = mapSize
        self.minDistance = minDistance

    def __call__(self, numSheeps):
        sampleOneAgentPosition = lambda:[round(x,2) for x in list(np.random.uniform(-self.mapSize, self.mapSize, self.positionDimension))]

        initWolfRandomPos = [sampleOneAgentPosition() for ID in range(self.numWolves)]
        initWolfZeroVel = lambda: np.zeros(self.positionDimension)
        initSheepRandomPos = [sampleOneAgentPosition() for sheepID in range(numSheeps)]
        initSheepRandomVel = lambda: np.random.uniform(0, 1, self.positionDimension)
        initBlockRandomPos = [sampleOneAgentPosition() for blockID in range(self.numBlocks)]
        initBlockZeroVel = lambda: np.zeros(self.positionDimension)

        for i, sheepPos in enumerate(initSheepRandomPos):
            while np.any(np.array([np.linalg.norm(np.array(agentPos) - np.array(sheepPos)) for agentPos in
                                   initWolfRandomPos]) < self.minDistance):
                sheepPos = sampleOneAgentPosition()
            initSheepRandomPos[i] = sheepPos
        agentsState = [state + vel for state, vel in
                       zip(initWolfRandomPos, [list(initWolfZeroVel()) for ID in range(self.numWolves)])]
        sheepState = [state + vel for state, vel in
                      zip(initSheepRandomPos, [list(initSheepRandomVel()) for sheepID in range(numSheeps)])]
        blockState = [state + vel for state, vel in
                      zip(initBlockRandomPos, [list(initBlockZeroVel()) for blockID in range(self.numBlocks)])]
        state = agentsState + sheepState + blockState
        agentInitCaughtHistory = 0
        for agentState in state:
            agentState.append(agentInitCaughtHistory)
        state = np.array(state)
        return state


class ResetMultiAgentNewtonChasingVariousSheep:
    def __init__(self, numWolves, numBlocks, mapSize, minDistance):
        self.positionDimension = 2
        self.numWolves = numWolves
        self.numBlocks = numBlocks
        self.mapSize = mapSize
        self.minDistance = minDistance

    def __call__(self, numSheeps):
        sampleOneAgentPosition = lambda:[round(x,2) for x in list(np.random.uniform(-self.mapSize, self.mapSize, self.positionDimension))]

        initWolfRandomPos = [sampleOneAgentPosition() for ID in range(self.numWolves)]
        initWolfZeroVel = lambda: np.zeros(self.positionDimension)
        initBlockRandomPos = [sampleOneAgentPosition() for blockID in range(self.numBlocks)]
        initBlockZeroVel = lambda: np.zeros(self.positionDimension)
        initSheepRandomPos = [sampleOneAgentPosition() for sheepID in range(numSheeps)]
        initSheepRandomVel = lambda: np.random.uniform(0, 1, self.positionDimension)

        for i, sheepPos in enumerate(initSheepRandomPos):
            while np.any(np.array([np.linalg.norm(np.array(agentPos) - np.array(sheepPos)) for agentPos in
                                   initWolfRandomPos]) < self.minDistance):
                sheepPos = sampleOneAgentPosition()
            initSheepRandomPos[i] = sheepPos
        agentsState = [state + vel for state, vel in
                       zip(initWolfRandomPos, [list(initWolfZeroVel()) for ID in range(self.numWolves)])]
        blockState = [state + vel for state, vel in
                       zip(initBlockRandomPos, [list(initBlockZeroVel()) for blockID in range(self.numBlocks)])]
        sheepState = [state + vel for state, vel in
                      zip(initSheepRandomPos, [list(initSheepRandomVel()) for sheepID in range(numSheeps)])]
        state = np.array(agentsState + sheepState + blockState)
        return state


class ResetMultiAgentChasingWithVariousSheep:
    def __init__(self, numWolves, numBlocks):
        self.positionDimension = 2
        self.numWolves = numWolves
        self.numBlocks = numBlocks

    def __call__(self, numSheep):
        self.numTotalAgents = self.numWolves + numSheep
        getAgentRandomPos = lambda: np.random.uniform(-1, +1, self.positionDimension)
        getAgentRandomVel = lambda: np.zeros(self.positionDimension)
        agentsStates = [list(getAgentRandomPos()) + list(getAgentRandomVel()) for ID in range(self.numTotalAgents)]

        getBlockRandomPos = lambda: np.random.uniform(-0.9, +0.9, self.positionDimension)
        getBlockSpeed = lambda: np.zeros(self.positionDimension)

        blocksState = [list(getBlockRandomPos()) + list(getBlockSpeed()) for blockID in range(self.numBlocks)]
        state = np.array(agentsStates + blocksState)
        return state


def samplePosition(gridSize, positionDimension):
    randomPos = lambda: np.random.uniform(0, gridSize - 1, positionDimension)
    position = list(randomPos())
    for i in range(positionDimension):
        position[i] = round(position[i], 2)
    return position


class ResetMultiAgentNewtonChasing:
    def __init__(self, gridSize, numWolves, minDistance):
        self.positionDimension = 2
        self.gridSize = gridSize
        self.numWolves = numWolves
        self.minDistance = minDistance

    def __call__(self, numSheeps):
        initWolfRandomPos = [samplePosition(self.gridSize, self.positionDimension) for ID in range(self.numWolves)]
        initWolfZeroVel = lambda: np.zeros(self.positionDimension)

        initSheepRandomPos = [samplePosition(self.gridSize, self.positionDimension) for sheepID in range(numSheeps)]
        initSheepRandomVel = lambda: np.random.uniform(0, 1, self.positionDimension)
        for i, sheepPos in enumerate(initSheepRandomPos):
            while np.all(np.array([np.linalg.norm(np.array(agentPos) - np.array(sheepPos)) for agentPos in
                                   initWolfRandomPos]) < self.minDistance):
                sheepPos = samplePosition(self.gridSize, self.positionDimension)
            initSheepRandomPos[i] = sheepPos
        agentsState = [state + vel for state, vel in
                       zip(initWolfRandomPos, [list(initWolfZeroVel()) for ID in range(self.numWolves)])]
        sheepState = [state + vel for state, vel in
                      zip(initSheepRandomPos, [list(initSheepRandomVel()) for ID in range(numSheeps)])]

        state = np.array(agentsState + sheepState)
        return state


class ResetStateWithCaughtHistory:
    def __init__(self, resetState, calSheepCaughtHistory):
        self.resetState = resetState
        self.calSheepCaughtHistory = calSheepCaughtHistory
    def __call__(self, numSheep):
        sheepsID = range(numSheep)
        self.calSheepCaughtHistory.getCaughtHistory = {sheepId: 0 for sheepId in sheepsID}
        return self.resetState()


class ResetStateAndReward:
    def __init__(self, resetState, rewardWolf):
        self.resetState = resetState
        self.rewardWolf = rewardWolf
    def __call__(self, numSheep):
        self.rewardWolf.getCaughtHistory = {sheepId:0 for sheepId in self.rewardWolf.sheepsID}
        return self.resetState(numSheep)


class IntegratedResetStateAndReward:
    def __init__(self, resetState, allWolfRewardFun):
        self.resetState = resetState
        self.allWolfRewardFun = allWolfRewardFun
    def __call__(self,numSheep):
        for key, rewardWolf in self.allWolfRewardFun.items():
            rewardWolf.getCaughtHistory = {sheepId:0 for sheepId in rewardWolf.sheepsID}
        return self.resetState(numSheep)


class Observe:
    def __init__(self, agentID, wolvesID, sheepsID, blocksID, getPosFromState, getVelFromAgentState):
        self.agentID = agentID
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.blocksID = blocksID
        self.getEntityPos = lambda state, entityID: getPosFromState(state[entityID])
        self.getEntityVel = lambda state, entityID: getVelFromAgentState(state[entityID])

    def __call__(self, state):
        blocksPos = [self.getEntityPos(state, blockID) for blockID in self.blocksID]
        agentPos = self.getEntityPos(state, self.agentID)
        blocksInfo = [blockPos - agentPos for blockPos in blocksPos]

        posInfo = []
        for wolfID in self.wolvesID:
            if wolfID == self.agentID: continue
            wolfPos = self.getEntityPos(state, wolfID)
            posInfo.append(wolfPos - agentPos)

        velInfo = []
        for sheepID in self.sheepsID:
            if sheepID == self.agentID: continue
            sheepPos = self.getEntityPos(state, sheepID)
            posInfo.append(sheepPos - agentPos)
            sheepVel = self.getEntityVel(state, sheepID)
            velInfo.append(sheepVel)

        agentVel = self.getEntityVel(state, self.agentID)
        # print(self.agentID,self.sheepsID,'state:', state)
        # print(self.agentID,self.sheepsID,'agentVel:' ,agentVel, 'agentPos:' ,agentPos, 'blocksInfo:' ,blocksInfo, 'posInfo:' ,posInfo, 'velInfo:' ,velInfo)
        return np.concatenate([agentVel] + [agentPos] + blocksInfo + posInfo + velInfo)


class ObserveWithCaughtHistory:
    def __init__(self, agentID, wolvesID, sheepsID, blocksID, getPosFromAgentState, getVelFromAgentState,
                 getCaughtHistoryFromAgentState):
        self.agentID = agentID
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.blocksID = blocksID
        self.getEntityPos = lambda state, entityID: getPosFromAgentState(state[entityID])
        self.getEntityVel = lambda state, entityID: getVelFromAgentState(state[entityID])
        self.getEntityCaughtHistory = lambda state, entityID: getCaughtHistoryFromAgentState(state[entityID])

    def __call__(self, state):
        # print('state', state)
        agentPos = self.getEntityPos(state, self.agentID)
        agentVel = self.getEntityVel(state, self.agentID)
        blocksPos = [self.getEntityPos(state, blockID) for blockID in self.blocksID]
        blocksInfo = [blockPos - agentPos for blockPos in blocksPos]

        posInfo = []
        for wolfID in self.wolvesID:
            if wolfID == self.agentID: continue
            wolfPos = self.getEntityPos(state, wolfID)
            posInfo.append(wolfPos - agentPos)

        velInfo = []
        caughtInfo = []
        for sheepID in self.sheepsID:
            if sheepID == self.agentID: continue
            sheepPos = self.getEntityPos(state, sheepID)
            posInfo.append(sheepPos - agentPos)
            sheepVel = self.getEntityVel(state, sheepID)
            velInfo.append(sheepVel)
            sheepCaughtHistory = self.getEntityCaughtHistory(state, sheepID)
            caughtInfo.append([sheepCaughtHistory])
        return np.concatenate([agentVel] + [agentPos] + blocksInfo + posInfo + velInfo + caughtInfo)


class GetCollisionForce:
    def __init__(self, contactMargin=0.001, contactForce=100):
        self.contactMargin = contactMargin
        self.contactForce = contactForce

    def __call__(self, obj1Pos, obj2Pos, obj1Size, obj2Size, obj1Movable, obj2Movable):
        posDiff = obj1Pos - obj2Pos
        dist = np.sqrt(np.sum(np.square(posDiff)))

        minDist = obj1Size + obj2Size
        penetration = np.logaddexp(0, -(dist - minDist) / self.contactMargin) * self.contactMargin

        force = self.contactForce * posDiff / dist * penetration
        force1 = +force if obj1Movable else None
        force2 = -force if obj2Movable else None

        return [force1, force2]


class ApplyActionForce:
    def __init__(self, wolvesID, sheepsID, entitiesMovableList, actionDim=2):
        self.agentsID = sheepsID + wolvesID
        self.numAgents = len(self.agentsID)
        self.entitiesMovableList = entitiesMovableList
        self.actionDim = actionDim

    def __call__(self, pForce, actions):
        self.numAgents = len(actions)
        self.agentsID = list(range(self.numAgents))
        noise = [None] * self.numAgents
        for agentID in self.agentsID:
            movable = self.entitiesMovableList[agentID]
            agentNoise = noise[agentID]
            if movable:
                agentNoise = np.random.randn(self.actionDim) * agentNoise if agentNoise else 0.0
                pForce[agentID] = np.array(actions[agentID]) + agentNoise
        return pForce


class ApplyEnvironForce:
    def __init__(self, numEntities, entitiesMovableList, entitiesSizeList, getCollisionForce, getPosFromState):
        self.numEntities = numEntities
        self.entitiesMovableList = entitiesMovableList
        self.entitiesSizeList = entitiesSizeList
        self.getCollisionForce = getCollisionForce
        self.getEntityPos = lambda state, entityID: getPosFromState(state[entityID])

    def __call__(self, pForce, state):
        self.numEntities = len(state)
        for entity1ID in range(self.numEntities):
            for entity2ID in range(self.numEntities):
                if entity2ID <= entity1ID: continue
                obj1Movable = self.entitiesMovableList[entity1ID]
                obj2Movable = self.entitiesMovableList[entity2ID]
                obj1Size = self.entitiesSizeList[entity1ID]
                obj2Size = self.entitiesSizeList[entity2ID]
                obj1Pos = self.getEntityPos(state, entity1ID)
                obj2Pos = self.getEntityPos(state, entity2ID)

                force1, force2 = self.getCollisionForce(obj1Pos, obj2Pos, obj1Size, obj2Size, obj1Movable, obj2Movable)

                if force1 is not None:
                    if pForce[entity1ID] is None: pForce[entity1ID] = 0.0
                    pForce[entity1ID] = force1 + pForce[entity1ID]

                if force2 is not None:
                    if pForce[entity2ID] is None: pForce[entity2ID] = 0.0
                    pForce[entity2ID] = force2 + pForce[entity2ID]

        return pForce


class IntegrateState:
    def __init__(self, numEntities, entitiesMovableList, massList, entityMaxSpeedList, getVelFromAgentState,
                 getPosFromAgentState, damping=0.25, dt=0.1):
        self.numEntities = numEntities
        self.entitiesMovableList = entitiesMovableList
        self.damping = damping
        self.dt = dt
        self.massList = massList
        self.entityMaxSpeedList = entityMaxSpeedList
        self.getEntityVel = lambda state, entityID: getVelFromAgentState(state[entityID])
        self.getEntityPos = lambda state, entityID: getPosFromAgentState(state[entityID])

    def __call__(self, pForce, state):
        self.numEntities = len(state)
        getNextState = lambda entityPos, entityVel: list(entityPos) + list(entityVel)
        nextState = []
        for entityID in range(self.numEntities):
            entityMovable = self.entitiesMovableList[entityID]
            entityVel = self.getEntityVel(state, entityID)
            entityPos = self.getEntityPos(state, entityID)

            if not entityMovable:
                nextState.append(getNextState(entityPos, entityVel))
                continue

            entityNextVel = entityVel * (1 - self.damping)
            entityForce = pForce[entityID]
            entityMass = self.massList[entityID]
            if entityForce is not None:
                entityNextVel += (entityForce / entityMass) * self.dt

            entityMaxSpeed = self.entityMaxSpeedList[entityID]
            if entityMaxSpeed is not None:
                speed = np.sqrt(np.square(entityNextVel[0]) + np.square(entityNextVel[1]))  #
                if speed > entityMaxSpeed:
                    entityNextVel = entityNextVel / speed * entityMaxSpeed

            entityNextPos = entityPos + entityNextVel * self.dt
            nextState.append(getNextState(entityNextPos, entityNextVel))

        return nextState


class IntegrateStateWithCaughtHistory:
    def __init__(self, numEntities, entitiesMovableList, massList, entityMaxSpeedList,  getVelFromAgentState, getPosFromAgentState,
                 calSheepCaughtHistory, damping=0.25, dt=0.05):
        self.numEntities = numEntities
        self.entitiesMovableList = entitiesMovableList
        self.damping = damping
        self.dt = dt
        self.massList = massList
        self.entityMaxSpeedList = entityMaxSpeedList
        self.getEntityVel = lambda state, entityID: getVelFromAgentState(state[entityID])
        self.getEntityPos = lambda state, entityID: getPosFromAgentState(state[entityID])
        self.calSheepCaughtHistory = calSheepCaughtHistory

    def __call__(self, pForce, state):
        getNextState = lambda entityPos, entityVel: list(entityPos) + list(entityVel)
        nextState = []
        sheepsID = range(len(self.calSheepCaughtHistory.wolvesID), len(state)-self.calSheepCaughtHistory.numBlock)
        for entityID in range(self.numEntities):
            entityMovable = self.entitiesMovableList[entityID]
            entityVel = self.getEntityVel(state, entityID)
            entityPos = self.getEntityPos(state, entityID)

            if not entityMovable:
                nextState.append(getNextState(entityPos, entityVel))
                continue

            entityNextVel = entityVel * (1 - self.damping)
            entityForce = pForce[entityID]
            entityMass = self.massList[entityID]
            if entityForce is not None:
                entityNextVel += (entityForce / entityMass) * self.dt

            entityMaxSpeed = self.entityMaxSpeedList[entityID]
            if entityMaxSpeed is not None:
                speed = np.sqrt(np.square(entityVel[0]) + np.square(entityVel[1]))
                if speed > entityMaxSpeed:
                    entityNextVel = entityNextVel / speed * entityMaxSpeed

            entityNextPos = entityPos + entityNextVel * self.dt
            nextState.append(getNextState(entityNextPos, entityNextVel))
        caughtHistory = self.calSheepCaughtHistory(state, nextState)
        for sheepID in sheepsID:
            nextState[sheepID].append(caughtHistory[sheepID])
        nextStateWithCaughtHistory = nextState.copy()
        return nextStateWithCaughtHistory


class TransitMultiAgentChasingForExpWithNoise:
    def __init__(self, reshapeWolfAction, reshapeSheepAction, applyActionForce, applyEnvironForce, integrateState, checkAllAgents, noiseAction):
        self.reshapeWolfAction = reshapeWolfAction
        self.reshapeSheepAction = reshapeSheepAction
        self.applyActionForce = applyActionForce
        self.applyEnvironForce = applyEnvironForce
        self.integrateState = integrateState
        self.checkAllAgents = checkAllAgents
        self.noiseAction = noiseAction

    def __call__(self, state, wolfAction, SheepAction,wolfForce,sheepForce):
        # print(state,actions)
        wolfAction = [self.reshapeWolfAction(action,wolfForce) for action in wolfAction]
        SheepAction = [self.reshapeSheepAction(action,sheepForce) for action in SheepAction]
        SheepAction = [self.noiseAction(action) for action in SheepAction]
        actions = wolfAction + SheepAction
        
        self.numEntities = len(state)
        p_force = [None] * self.numEntities
        p_force = self.applyActionForce(p_force, actions)
        p_force = self.applyEnvironForce(p_force, state)
        nextState = self.integrateState(p_force, state)
        nextState = self.checkAllAgents(nextState)
        return nextState


class TransitMultiAgentChasingForExpVariousForce:
    def __init__(self, reshapeHumanAction, reshapeSheepAction, applyActionForce, applyEnvironForce, integrateState, checkAllAgents):
        self.reshapeHumanAction = reshapeHumanAction
        self.reshapeSheepAction = reshapeSheepAction
        self.applyActionForce = applyActionForce
        self.applyEnvironForce = applyEnvironForce
        self.integrateState = integrateState
        self.checkAllAgents = checkAllAgents

    def __call__(self, state, humanAction, SheepAction, wolfForce, sheepForce):
        humanAction = [self.reshapeHumanAction(action,wolfForce) for action in humanAction]
        SheepAction = [self.reshapeSheepAction(action,sheepForce) for action in SheepAction]

        actions = humanAction + SheepAction
        self.numEntities = len(state)
        p_force = [None] * self.numEntities
        p_force = self.applyActionForce(p_force, actions)
        p_force = self.applyEnvironForce(p_force, state)
        nextState = self.integrateState(p_force, state)
        nextState = self.checkAllAgents(nextState)
        return nextState


class TransitMultiAgentChasingForExp:
    def __init__(self, reshapeHumanAction, reshapeSheepAction, applyActionForce, applyEnvironForce, integrateState, checkAllAgents):
        self.reshapeHumanAction = reshapeHumanAction
        self.reshapeSheepAction = reshapeSheepAction
        self.applyActionForce = applyActionForce
        self.applyEnvironForce = applyEnvironForce
        self.integrateState = integrateState
        self.checkAllAgents = checkAllAgents

    def __call__(self, state, humanAction, SheepAction):
        # print(state,actions)
        humanAction = [self.reshapeHumanAction(action) for action in humanAction]
        SheepAction = [self.reshapeSheepAction(action) for action in SheepAction]
        # actions = [self.reshapeAction(action) for action in actions]
        actions = humanAction + SheepAction
        self.numEntities = len(state)
        p_force = [None] * self.numEntities
        p_force = self.applyActionForce(p_force, actions)
        p_force = self.applyEnvironForce(p_force, state)
        nextState = self.integrateState(p_force, state)
        nextState = self.checkAllAgents(nextState)
        return nextState


class TransitMultiAgentChasing:
    def __init__(self, numEntities, reshapeAction, applyActionForce, applyEnvironForce, integrateState):
        self.numEntities = numEntities
        self.reshapeAction = reshapeAction
        self.applyActionForce = applyActionForce
        self.applyEnvironForce = applyEnvironForce
        self.integrateState = integrateState

    def __call__(self, state, actions):
        self.numEntities = len(state)
        actions = [self.reshapeAction(action) for action in actions]
        p_force = [None] * self.numEntities
        p_force = self.applyActionForce(p_force, actions)
        p_force = self.applyEnvironForce(p_force, state)
        nextState = self.integrateState(p_force, state)

        return nextState

class ReshapeActionVariousForce:
    def __init__(self):
        self.actionDim = 2
        # self.sensitivity = 1

    def __call__(self, action, sensitivity):  # action: tuple of dim (5,1)
        actionX = action[1] - action[2]
        actionY = action[3] - action[4]
        actionReshaped = np.array([actionX, actionY]) * sensitivity
        return actionReshaped


class ReshapeHumanAction:
    def __init__(self):
        self.actionDim = 2
        self.sensitivity = 5

    def __call__(self, action):  # action: tuple of dim (5,1)
        actionX = action[1] - action[2]
        actionY = action[3] - action[4]
        actionReshaped = np.array([actionX, actionY]) * self.sensitivity
        return actionReshaped

class ReshapeWolfAction:
    def __init__(self):
        self.actionDim = 2
        self.sensitivity = 5

    def __call__(self, action):  # action: tuple of dim (5,1)
        actionX = action[1] - action[2]
        actionY = action[3] - action[4]
        actionReshaped = np.array([actionX, actionY]) * self.sensitivity
        return actionReshaped

class ReshapeSheepAction:
    def __init__(self):
        self.actionDim = 2
        self.sensitivity = 5

    def __call__(self, action):  # action: tuple of dim (5,1)
        actionX = action[1] - action[2]
        actionY = action[3] - action[4]
        actionReshaped = np.array([actionX, actionY]) * self.sensitivity
        return actionReshaped


class BuildGaussianFixCov:
        def __init__(self, cov):
            self.cov = cov

        def __call__(self, mean):
            return ss.multivariate_normal(mean, self.cov)


def sampleFromContinuousSpace(distribution):
        return distribution.rvs()


class ComposeCentralControlPolicyByGaussianOnDeterministicAction:
    def __init__(self, reshapeAction, observe, actOneStepOneModel, buildGaussian):
        self.reshapeAction = reshapeAction
        self.observe = observe
        self.actOneStepOneModel = actOneStepOneModel
        self.buildGaussian = buildGaussian

    def __call__(self, individualModels, numAgentsInWe):
        centralControlPolicy = lambda state: [self.buildGaussian(tuple(self.reshapeAction(
            self.actOneStepOneModel(individualModels[agentId], self.observe(state))))) for agentId in range(numAgentsInWe)]
        return centralControlPolicy
