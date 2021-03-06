import json
import re
import os
from lxml import etree

class AIFParser:

    def __init__(self, corpusName):

        self.relationNodeDict = {}
        self.propositionDict = {}
        self.corpusName = corpusName

        self.allowUndercuts = True

        self.DEFAULT_INFERENCE_NUMBER = 72
        self.DEFAULT_CONFLICT_NUMBER = 71

        self.DEFAULT_INFERENCE = "Default Inference"
        self.DEFAULT_CONFLICT = "Default Conflict"

    def startParsing(self, annotationFile, originalTextFile):

        with open(annotationFile) as data_file:
            data = json.load(data_file)

        if not os.path.exists(originalTextFile):

            textInput ="..."

        else:
            with open(originalTextFile, encoding='ISO-8859-1') as tf:
                textInput = tf.readlines()

        self.originalText = re.sub(' +',' ',"".join(textInput))

        self.relationNodeDict = {}
        self.propositionDict = {}

        premiseCandidates = list()
        claimCandidates = list()

        for node in range(len(data["nodes"])):

            if self.isPropositionNode(data["nodes"][node]["type"]):

                propositionKey = data["nodes"][node]["nodeID"]

                self.propositionDict[propositionKey] = {}

                formattedText =re.sub(' +',' ', data["nodes"][node]["text"])

                pat = r"\W+".join([re.escape(x) for x in formattedText.split()])

                match = re.search(pat, self.originalText)

                if match != None:

                    start = match.span()[0]

                    end = match.span()[1]

                    self.propositionDict[propositionKey]["text"] = self.originalText[start:end]

                else:

                    start = -1
                    end = -1

                    self.propositionDict[propositionKey]["text"] = formattedText

                self.propositionDict[propositionKey]["positionStart"] = start

                self.propositionDict[propositionKey]["positionEnd"] = end

                self.propositionDict[propositionKey]["Relation"] = {}


            elif self.isRelationNode(data["nodes"][node]["type"]):

                if data["nodes"][node]["text"] == "RA":

                    text = self.DEFAULT_INFERENCE
                    label = "0"

                elif data["nodes"][node]["text"] == "CA":

                    text = self.DEFAULT_CONFLICT
                    label = "1"

                elif ((data["nodes"][node]["text"] == self.DEFAULT_INFERENCE) or (data["nodes"][node]["type"] == "RA")):

                    text = self.DEFAULT_INFERENCE
                    label = "0"

                elif ((data["nodes"][node]["text"] == self.DEFAULT_CONFLICT) or (data["nodes"][node]["type"] == "CA")):

                    text = self.DEFAULT_CONFLICT
                    label = "1"

                else:

                    text = data["nodes"][node]["text"]
                    schemeID = data["nodes"][node]["schemeID"]

                    # attack relation label is 1
                    if schemeID == "71":
                        label = "1"

                    # support relation label is 0
                    else:
                        label = "0"

                relationKey = data["nodes"][node]["nodeID"]

                self.relationNodeDict[relationKey] = {}

                self.relationNodeDict[relationKey]["text"] = text

                self.relationNodeDict[relationKey]["type"] = data["nodes"][node]["type"]

                self.relationNodeDict[relationKey]["label"] = label

                self.relationNodeDict[relationKey]["incomingNodes"] = []


        undercutList = list()

        for relation in range(len(data["edges"])):

            fromNode = data["edges"][relation]["fromID"]
            toNode = data["edges"][relation]["toID"]

            if (fromNode in self.propositionDict.keys()) and (toNode in self.relationNodeDict.keys()):

                self.relationNodeDict[toNode]["incomingNodes"].append(fromNode)

                premiseCandidates.append(fromNode)

            elif (toNode in self.propositionDict.keys()) and (fromNode in self.relationNodeDict.keys()):

                self.relationNodeDict[fromNode]["outgoingNode"] = toNode

                claimCandidates.append(toNode)

            elif (toNode in self.relationNodeDict.keys()) and (fromNode in self.relationNodeDict.keys()):

                self.relationNodeDict[fromNode]["outgoingNode"] = toNode
                self.relationNodeDict[toNode]["incomingNodes"].append(fromNode)

                undercutList.append(fromNode)

        if not self.allowUndercuts:

            for relationNode in undercutList:
                self.eliminateUndercuts(relationNode)

        premiseNodes = list(set(premiseCandidates) - set(claimCandidates))
        conclusionNodes = list(set(claimCandidates) - set(premiseCandidates))
        claimNodes = list(set(claimCandidates) - set(conclusionNodes))

        for proposition in self.propositionDict.keys():

            hasOutgoingRelation = True

            if proposition in conclusionNodes:

                self.propositionDict[proposition]["type"] = "conclusion"

                hasOutgoingRelation = False

            elif proposition in claimNodes:

                self.propositionDict[proposition]["type"] = "claim"

            else:

                self.propositionDict[proposition]["type"] = "premise"

            if hasOutgoingRelation:

                for relation in self.relationNodeDict.keys():

                    if proposition in self.relationNodeDict[relation]["incomingNodes"]:

                        if self.relationNodeDict[relation]["outgoingNode"] != proposition:

                            self.propositionDict[proposition]["Relation"][relation] = {}
                            self.propositionDict[proposition]["Relation"][relation]["type"] = self.relationNodeDict[relation]["text"]
                            self.propositionDict[proposition]["Relation"][relation]["label"] = self.relationNodeDict[relation]["label"]
                            self.propositionDict[proposition]["Relation"][relation]["partnerID"] = self.relationNodeDict[relation]["outgoingNode"]

                            if self.relationNodeDict[relation]["label"] == "1" and self.propositionDict[proposition]["type"] == "premise":
                                self.propositionDict[proposition]["type"] = "claim"


        argumentationDict = self.sortDictionaries(conclusionNodes, premiseNodes, claimNodes)

        xmlData = self.parseToXML(argumentationDict)

        return xmlData

    def sortDictionaries(self, conclusionNodes, premiseNodes, claimNodes):

        argDict = {}

        for conclusion in conclusionNodes:

            argDict[conclusion] = set()

            for claim in claimNodes:

                if self.isPartOfArgument(claim, conclusion):

                    argDict[conclusion].add(claim)

            for premise in premiseNodes:

                if self.isPartOfArgument(premise, conclusion):

                    argDict[conclusion].add(premise)

        return argDict

    def eliminateUndercuts(self, relationNode):

        if self.relationNodeDict[relationNode]["outgoingNode"] in self.relationNodeDict.keys():

            undercut = self.relationNodeDict[relationNode]["outgoingNode"]

            if len(self.relationNodeDict[undercut]["incomingNodes"]) > 2:

                if self.relationNodeDict[undercut]["label"] == "1":

                    self.relationNodeDict[relationNode]["text"] = self.DEFAULT_INFERENCE

                    self.relationNodeDict[relationNode]["label"] = "0"

                self.relationNodeDict[relationNode]["outgoingNode"] = self.relationNodeDict[undercut]["outgoingNode"]

            else:

                toRelate = self.relationNodeDict[undercut]["outgoingNode"]

                for node in self.relationNodeDict[undercut]["incomingNodes"]:

                    if node not in self.relationNodeDict.keys():
                        toRelate = node

                self.relationNodeDict[relationNode]["outgoingNode"] = toRelate


            if self.relationNodeDict[undercut]["outgoingNode"] in self.relationNodeDict.keys():

                self.eliminateUndercuts(self, self.relationNodeDict[undercut]["outgoingNode"])

    def isPartOfArgument(self, proposition, conclusion):

        if (proposition not in self.relationNodeDict.keys()):

            if proposition == conclusion:
                return True

            elif len(self.propositionDict[proposition]["Relation"].keys())== 0:

                return False

            else:

                returnValue = False

                for relationKey in self.propositionDict[proposition]["Relation"].keys():

                    if conclusion == self.propositionDict[proposition]["Relation"][relationKey]["partnerID"]:

                        returnValue = True

                    else:

                        returnValue = self.isPartOfArgument(self.propositionDict[proposition]["Relation"][relationKey]["partnerID"], conclusion)
        else:

            vather = self.relationNodeDict[proposition]["outgoingNode"]
            returnValue = self.isPartOfArgument(vather, conclusion)

        return returnValue

    def isRelationNode(self, nodeType):

        return (nodeType == "RA" or nodeType == "CA")

    def isPropositionNode(self, nodeType):

         return (nodeType == "I")

    def parseToXML(self, argumentationDict):

        root = etree.Element('Annotation')
        root.set("corpus", self.corpusName)
        uniquePropositions = list()

        for conclusion in argumentationDict.keys():

            proposition = etree.Element('Proposition')
            proposition.set("id", conclusion)
            root.append(proposition)

            aduType = etree.Element('ADU')
            aduType.set("type", self.propositionDict[conclusion]["type"])
            proposition.append(aduType)

            text = etree.Element('text')
            text.text = self.propositionDict[conclusion]["text"]
            proposition.append(text)

            textPosition = etree.Element('TextPosition')
            textPosition.set("start", str(self.propositionDict[conclusion]["positionStart"]))
            textPosition.set("end", str(self.propositionDict[conclusion]["positionEnd"]))
            proposition.append(textPosition)

            for proposition in argumentationDict[conclusion]:

                propositionKey = str(proposition)

                proposition = etree.Element('Proposition')
                proposition.set("id", propositionKey)
                root.append(proposition)

                aduType = etree.Element('ADU')
                aduType.set("type", self.propositionDict[propositionKey]["type"])
                proposition.append(aduType)

                text = etree.Element('text')
                text.text = self.propositionDict[propositionKey]["text"]
                proposition.append(text)

                textPosition = etree.Element('TextPosition')
                textPosition.set("start", str(self.propositionDict[propositionKey]["positionStart"]))
                textPosition.set("end", str(self.propositionDict[propositionKey]["positionEnd"]))
                proposition.append(textPosition)

                for relationKey in self.propositionDict[propositionKey]["Relation"].keys():

                    propositionRelations = self.propositionDict[propositionKey]["Relation"]

                    relation = etree.Element('Relation')
                    relation.set("relationID", relationKey)
                    relation.set("type", propositionRelations[relationKey]["type"])
                    relation.set("stance", propositionRelations[relationKey]["label"])
                    relation.set("partnerID", propositionRelations[relationKey]["partnerID"])
                    proposition.append(relation)

        originalTextNode = etree.Element('OriginalText')
        originalTextNode.text = "".join(self.originalText)
        root.append(originalTextNode)

        xmlData = etree.tostring(root, pretty_print=True)

        return xmlData
