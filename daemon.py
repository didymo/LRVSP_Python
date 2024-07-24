import spacy
import mysql.connector
import time
import logging
import base64
import subprocess
import re
import math

from timeit import default_timer as timer
from types import FunctionType as function

import processPDF as pdf
from config import DRUPAL_PATH, LOG_PATH, DB_CONFIG

CYCLE_TIME = 120
PARSE_LIMIT = 10
CREATE_LIMIT = 30

# supported file types:
# dictionary with file type extension as key and function to process that type it as value
FILE_TYPES: dict[str, function] = {
    "pdf": pdf.process
}

GET_PATHS_QUERY = '''SELECT * FROM FilePaths LIMIT {}'''
DROP_PATH_QUERY = '''DELETE FROM FilePaths WHERE ID = {}'''
MAKE_DOC_QUERY = '''INSERT INTO DocObjs (title, metadata, entityId, numLinks) VALUES ("{}", "{}", {}, {})'''
MAKE_LINK_QUERY = '''INSERT INTO LinkObjs (fromTitle, toTitle) VALUES ("{}", "{}")'''
CHECK_REMAINING_QUERY = '''SELECT SUM(rowCount) FROM (SELECT COUNT(*) AS rowCount FROM FilePaths
                                               UNION ALL
                                               SELECT COUNT(*) AS rowCount FROM DocObjs
                                               UNION ALL
                                               SELECT COUNT(*) AS rowCount FROM LinkObjs) AS tmp'''

def timeNow():
    return time.ctime(time.time())

nlp = spacy.load("en_LRVSP_spacy")

logger = logging.getLogger("LRVSP_Python")
logging.basicConfig(filename=f"{LOG_PATH}", encoding="utf8", level=logging.DEBUG)

logger.info(f"\t{timeNow()}\t| Start daemon")

try:
    while True:
            startTime = timer()
            logger.info(f"\t{timeNow()}\t| Start processing")
            # open database connection
            cnx = mysql.connector.connect(**DB_CONFIG)
            cursor = cnx.cursor()
            # get filepaths to process
            cursor.execute(GET_PATHS_QUERY.format(PARSE_LIMIT))
            results = [res for res in cursor] # extract all results in cursor iterator so we can use it for other things
            for res in results:
                # get results
                pathId: int = res[0]
                file: str = res[1]
                entId: int = res[2]
                # get file name (and b64 encode it for later)
                name = file.split('/')[-1]
                # get file type
                fType = name.split('.')[-1].lower()
                # remove suffixes and filetype from file name for entity creation
                fileName = name.removesuffix(f".{fType}")
                fileId = re.search(r"_\d+$",fileName,re.MULTILINE)
                if fileId:
                    fileName = fileName.removesuffix(fileId.group(0))
                b64Name = base64.b64encode(fileName.encode()).decode()
                text = file
                if fType in FILE_TYPES:
                    logger.info(f"\t{timeNow()}\t| Processing new {fType}: {name.removesuffix(fType)}")
                    text = FILE_TYPES[fType](file)
                else:
                    logger.error(f"\t{timeNow()}\t| Unsupported File type: {fType}")
                    continue
                if not isinstance(text, str):
                    logger.error(f"\t{timeNow()}\t| File processing did not complete. Expected str, got {type(text)}")
                    continue
                # remove path from database
                cursor.execute(DROP_PATH_QUERY.format(pathId))
                # extract links
                doc = nlp(text)
                links = set([ent.text for ent in doc.ents if ent.label_ == "ref_doc" and 4*math.ceil((len(ent.text)/3)) < 255])
                metadata = base64.b64encode("".encode()).decode() # empty metadata string
                # push new DocObj to database
                cursor.execute(MAKE_DOC_QUERY.format(b64Name,metadata,entId,len(links)))
                # push links to database
                for link in links:
                    b64Link = base64.b64encode(link.encode()).decode()
                    cursor.execute(MAKE_LINK_QUERY.format(b64Name,b64Link))
            cnx.commit()
            # tell drupal to start processing
            result = subprocess.run([f"{DRUPAL_PATH}/vendor/bin/drush","lrvsCheck-db",str(CREATE_LIMIT)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if result.returncode == 0:
                res = result.stdout
                if isinstance(res, bytes): res = res.decode()
                logger.info(f"\t{timeNow()}\t| {res}")
            else:
                res = result.stderr
                if isinstance(res, bytes): res = res.decode()
                logger.error(f"\t{timeNow()}\t| Drush failed with error code {result.returncode} {res}")
            endTime = timer()
            timeTaken = endTime-startTime
            logger.info(f"\t{timeNow()}\t| End processing. Time taken {timeTaken:.4f} seconds")
            # check if there's still stuff to process, if there is immediately re-run
            cursor.execute(CHECK_REMAINING_QUERY)
            rowsLeft = next(cursor)
            cnx.close()
            if rowsLeft[0] == 0:
                time.sleep(CYCLE_TIME-min(CYCLE_TIME,timeTaken))

except KeyboardInterrupt:
    logger.info(f"\t{timeNow()}\t| Received keyboard interrupt, closing daemon")
    