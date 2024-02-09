from abc import ABC, abstractmethod 
import os
import re

class UrlHandler(ABC): 
    @abstractmethod
    def test(self, url) -> bool:
        return False;
    @abstractmethod
    def work(self, url):
        pass

class DefaultHandler(UrlHandler):
    def test(self, art):
        return True
    def work(self, index, art):
        # TODO clean this up
        from generator import loadordownload,extract,removeEmptyLines,splitFirstSentenceParagraph,extract_metadata,asset_dir,isValidDictItem,faSymbolPerHostname

        sitecontent= loadordownload(index, art)
        data  = extract(sitecontent)

        if data is None:
            data = ""

        # temp remove all emoji stuff, until found decent solutions in latex
        # solved : no longer necessary with Tectonic Typesetting.
        # data = removeUnicode(data)
        # data can contain a lot of characters, we only want the first 1500
        data = data[0:min(1100, len(data))]
        # santize the data by removing % and / 
        data = data.replace("%", "")
        data = data.replace("\\", "")

        # remove empty lines
        data = removeEmptyLines(data)
        firstSentence, data = splitFirstSentenceParagraph(data)

        # the string art.title might contain text and numbers  of the format "Votes: 521 Comments: 83"
        # we want to extract the numbers
        votes= 0
        comments = 0
        if (art.title is not None):
            numbers = re.findall(r'\d+', art.title) 
            if (len(numbers) ==2):
                votes = int(numbers[0])
                comments = int(numbers[1])

        metadata = extract_metadata(sitecontent)
        if metadata is None:
            metadatadict   = {}
        else:
            metadatadict = metadata.as_dict()
        
        # we extend the metadata with the votes and comments counts if they are > 0
        if (votes > 0):
            metadatadict["votes"] = votes
        if (comments > 0):
            metadatadict["comments"] = comments

        # fall back 
        image = "notfound.png"
        #image url can be either a png or a jpg
        if os.path.isfile(f'{asset_dir}{index}.png'):
            image = f'{asset_dir}{index}.png'
        
        if os.path.isfile(f'{asset_dir}{index}.jpg'):
            image = f'{asset_dir}{index}.jpg'

        #potential interested metadata fields are: author, date, image, sitename
        #not used , but for future reference : 
        # pagetype [object, article, website ]
        # description
        # categories and tags

        newsproperties = []
        
        if (isValidDictItem("author", metadatadict)): 
            newsproperties.append({ "symbol": "User", "value" : metadatadict["author"], "url": None})
        if (isValidDictItem("date", metadatadict)):
            newsproperties.append({ "symbol": "Calendar", "value" : metadatadict["date"], "url": None})
        if (isValidDictItem("hostname", metadatadict)):
            newsproperties.append({ "symbol": faSymbolPerHostname(metadatadict["hostname"]), "value" : metadatadict["hostname"], "url": None})
        if ("votes" in metadatadict):
            newsproperties.append({ "symbol": "ThumbsOUp", "value" : metadatadict["votes"], "url": art.suburl})
        if ("comments" in metadatadict):
            newsproperties.append({ "symbol": "Comments", "value" : metadatadict["comments"], "url": art.suburl})

        return {
                "title": art.text, 
                "url" : art.mainurl,
                "image": image, 
                "category" : art.category,
                "firstline": firstSentence,
                "content": data, 
                "properties": newsproperties 
            }