# hackernewspaper

This is the hacker**news**letter but in the format of a magazine, a pdf edition. Well, at least I tried to look like a magazine :smile: 
The latex based pdf contains the hackernewsletter edition including the categories, screenshots of all the url's, some metadata, and the  'gather' text from the url, but don't expect too much of the text sofar.

As an example: [HackerNewsPaper-667](https://github.com/bitfox-git/hackernewspaper/releases/download/667/HackerNewsPaper-667.pdf).
All the hackernewspaper editions can be found [here](https://github.com/bitfox-git/hackernewspaper/releases), in the releases of this repo. 

## Motivation

I :heart: the hacker**news**letter. But I also cannot remember the links I've already opened, viewed, readed, watched. Only the name of the link in the email is not enough (for me..) to memorize what i've seen and not. But I do remember, as soon as the page opens in the browser, at that moment, i can exactly recall most of it. I just wanted to have a quicker overview of the newsletter. And the screenshots of the url's helps me achieve this. 

But ended up with much more....

## Screenshots
I use `playwright` to generate screenshots of the links.
Or `pythumb` in case of a YouTube link, to get the main thumb of the video.

## Credits
Praise and credits for [Kale Davis](http://www.kaledavis.com), as he is doing all the hard work of handpicking/organizing the articles each week. 
If you like this hacker**news***paper*, please also subscribe to the original hacker**news**letter at [hackernewsletter.com](https://hackernewsletter.com)!
Disclaimer: Hackernewsletter and Hackernewspaper are not affiliated with Y Combinator in any way.

## Want to help?
I'm not a Latex expert. And there are also a lot of nice to have refinements to think of:
- [ ] Parsing the top content (some times Kale leaves a message) on the top of his newsletter, is not done. 
- [ ] Parsing the sponsor content is sometimes off..
- [ ] Nicer output , more layouts in the template
- [ ] Solve the GDPR Cookie problems on some screenshot. 
- [ ] Better text formatting. Maybe with the help of a LLM? 
- [ ] For non-html links, devise another method to generate a screenshot and extract text and metadata. The link in the newsletter is not always pointing to html content (think of direct links to MP4 files, PDF files, etc. )       
- [ ] In case of YouTube / Vimeo url's , get the duration as metadata + description from the platform. Which requires a Youtube Video API v3 key...

