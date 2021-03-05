from .SampleAnnotation import SampleAnnotation
from .submodules import *
from .ExportCounts import ExportCounts
from drop import utils
from pathlib import Path
import wbuild
from snakemake.logging import logger                                                                                    



class DropConfig:
    CONFIG_KEYS = [
        # wbuild keys
        "projectTitle", "htmlOutputPath", "scriptsPath", "indexWithFolderName", "fileRegex", "readmePath",
        # global parameters
        "root", "sampleAnnotation", "geneAnnotation", "genomeAssembly", "exportCounts", "tools", "hpoFile","genome",
        # modules
        "aberrantExpression", "aberrantSplicing", "mae"
    ]

    def __init__(self, wbuildConfig):
        """
        Parse wbuild/snakemake config object for DROP-specific content
        :param wbuildConfig: wBuild config object
        """

        self.wBuildConfig = wbuildConfig
        self.config_dict = self.setDefaults(wbuildConfig.getConfig())

        self.root = Path(self.get("root"))
        self.processedDataDir = self.root / "processed_data"
        self.processedResultsDir = self.root / "processed_results"
        utils.createDir(self.root)
        utils.createDir(self.processedDataDir)
        utils.createDir(self.processedResultsDir)

        self.htmlOutputPath = Path(self.get("htmlOutputPath"))
        self.readmePath = Path(self.get("readmePath"))

        # annotations
        self.geneAnnotation = self.get("geneAnnotation")
        self.genomeAssembly = self.get("genomeAssembly")
        self.sampleAnnotation = SampleAnnotation(self.get("sampleAnnotation"), self.root)

        # config defined genome paths
        self.genomeFiles = self.getGenomeFiles()

        # submodules
        self.AE = AE(
            config=self.get("aberrantExpression"),
            sampleAnnotation=self.sampleAnnotation,
            processedDataDir=self.processedDataDir,
            processedResultsDir=self.processedResultsDir
        )

        self.AS = AS(
            config=self.get("aberrantSplicing"),
            sampleAnnotation=self.sampleAnnotation,
            processedDataDir=self.processedDataDir,
            processedResultsDir=self.processedResultsDir
        )
        self.MAE = MAE(
            config=self.get("mae"),
            sampleAnnotation=self.sampleAnnotation,
            processedDataDir=self.processedDataDir,
            processedResultsDir=self.processedResultsDir,
            genomeFiles=self.genomeFiles
        )

        # counts export
        self.exportCounts = ExportCounts(
            dict_=self.get("exportCounts"),
            outputRoot=self.processedResultsDir,
            sampleAnnotation=self.sampleAnnotation,
            geneAnnotations=self.getGeneAnnotations(),
            genomeAssembly=self.get("genomeAssembly"),
            aberrantExpression=self.AE,
            aberrantSplicing=self.AS
        )

        # write sample params for each module
        #self.AE.writeSampleParams(self.geneAnnotation)

        sampleParams = {}
        for ann in self.geneAnnotation:
            annParams = {self.AE.name :{
                                        "countParams": 
                                            [self.AE,
                                             self.processedDataDir/"aberrant_expression"/f"{ann}"/"params/counts",
                                             ["RNA_ID"],
                                             True,
                                             False
                                            ],
                                        "mergeParams":
                                            [self.AE,
                                             self.processedDataDir/"aberrant_expression"/f"{ann}"/"params/merge",
                                             ["RNA_ID", "RNA_BAM_FILE","COUNT_MODE", "PAIRED_END", "COUNT_OVERLAPS", "STRAND"],
                                             True,
                                             True
                                            ],
                                        "resultParams": 
                                            [self.AE,
                                             self.processedDataDir/"aberrant_expression"/f"{ann}"/"params/results",
                                             ["RNA_BAM_FILE", "DNA_VCF_FILE","DROP_GROUP","COUNT_MODE",
                                              "PAIRED_END", "COUNT_OVERLAPS", "STRAND"],
                                             False, #include 
                                             True # grouped 
                                            ]
                                           },
                          self.MAE.name:{
                                        "sampleParams":
                                            [self.MAE,
                                             self.processedDataDir/"mae/params/snvs",
                                             ["RNA_ID","DNA_ID","RNA_BAM_FILE", "DNA_VCF_FILE","GENOME"],
                                             True, #include the columns above (if False take compliment)
                                             False # grouped 
                                            ],
                                        "resultParams":
                                            [self.MAE,
                                             self.processedDataDir/"mae/params/results",
                                             ["RNA_BAM_FILE", "DNA_VCF_FILE","DROP_GROUP","COUNT_MODE",
                                             "PAIRED_END", "COUNT_OVERLAPS", "STRAND"], #columns for params
                                             False, #include the columns above (if False take compliment)
                                             True # grouped 
                                            ]
                                           }
                                              
                         }
            sampleParams[ann] = annParams
             

        for ann in sampleParams:
            for module in sampleParams[ann]:
                for suffix in sampleParams[ann][module]:
                    module_obj,path,params,include,group_param = sampleParams[ann][module][suffix]
                    module_obj.writeSampleParams(path,params,include,suffix,group_param = group_param)
        # legacy
        utils.setKey(self.config_dict, None, "aberrantExpression", self.AE.dict_)
        utils.setKey(self.config_dict, None, "aberrantSplicing", self.AS.dict_)
        utils.setKey(self.config_dict, None, "mae", self.MAE.dict_)

    def setDefaults(self, config_dict):
        """
        Check mandatory keys and set defaults for any missing keys
        :param config_dict: config dictionary
        :return: config dictionary with defaults
        """
        # check mandatory keys
        config_dict = utils.checkKeys(config_dict, keys=["htmlOutputPath", "root", "sampleAnnotation"],
                                      check_files=True)
        config_dict["geneAnnotation"] = utils.checkKeys(config_dict["geneAnnotation"], keys=None, check_files=True)

        config_dict["wBuildPath"] = utils.getWBuildPath()

        setKey = utils.setKey
        setKey(config_dict, None, "fileRegex", r".*\.(R|md)")
        setKey(config_dict, None, "genomeAssembly", "hg19")
        hpo_url = 'https://www.cmm.in.tum.de/public/paper/drop_analysis/resource/hpo_genes.tsv.gz'
        setKey(config_dict, None, "hpoFile", hpo_url)

        # set submodule dictionaries
        setKey(config_dict, None, "aberrantExpression", dict())
        setKey(config_dict, None, "aberrantSplicing", dict())
        setKey(config_dict, None, "mae", dict())
        setKey(config_dict, None, "exportCounts", dict())

        # commandline tools
        setKey(config_dict, None, "tools", dict())
        setKey(config_dict, ["tools"], "samtoolsCmd", "samtools")
        setKey(config_dict, ["tools"], "bcftoolsCmd", "bcftools")
        setKey(config_dict, ["tools"], "gatkCmd", "gatk")

        return config_dict

    def getRoot(self, str_=True):
        return utils.returnPath(self.root, str_=str_)

    def getProcessedDataDir(self, str_=True):
        return utils.returnPath(self.processedDataDir, str_=str_)

    def getProcessedResultsDir(self, str_=True):
        return utils.returnPath(self.processedResultsDir, str_=str_)

    def getHtmlOutputPath(self, str_=True):
        return utils.returnPath(self.htmlOutputPath, str_=str_)

    def getHtmlFromScript(self, path, str_=True):
        path = Path(path).with_suffix(".html")
        file_name = wbuild.utils.pathsepsToUnderscore(str(path), dotsToUnderscore=False)
        html_output_path = self.getHtmlOutputPath(str_=False)
        return utils.returnPath(html_output_path / file_name, str_=str_)

    def get(self, key):
        if key not in self.CONFIG_KEYS:
            raise KeyError(f"'{key}' not defined for DROP config")
        return self.wBuildConfig.get(key)

    def getTool(self, tool):
        try:
            toolCmd = self.get("tools")[tool]
        except KeyError:
            raise KeyError(f"'{toolCmd}' not a defined tool for DROP config")
        return toolCmd

    def getGeneAnnotations(self):
        return self.geneAnnotation

    def getGeneVersions(self):
        return self.geneAnnotation.keys()

    def getGeneAnnotationFile(self, annotation):
        return self.geneAnnotation[annotation]

    def getFastaFiles(self):
        if isinstance(self.genomeFiles,str):
            return {self.genomeFiles:self.genomeFiles}
        else:
            return self.genomeFiles

    def getFastaDict(self, fasta_file):
        return self.getGenomeDict(fasta_file)

    def getBSGenomeName(self):
        assemblyID = self.get("genomeAssembly")

        if assemblyID == 'hg19':
            return "BSgenome.Hsapiens.UCSC.hg19"
        if assemblyID == 'hs37d5':
            return "BSgenome.Hsapiens.1000genomes.hs37d5"
        if assemblyID == 'hg38':
            return "BSgenome.Hsapiens.UCSC.hg38"
        if assemblyID == 'GRCh38':
            return "BSgenome.Hsapiens.NCBI.GRCh38"
        
        raise ValueError("Provided genome assembly not known: " + assemblyID)
 
    def getBSGenomeVersion(self):
        assemblyID = self.get("genomeAssembly")

        if assemblyID in ['hg19', 'hs37d5']:
            return 37
        if assemblyID in ['hg38', 'GRCh38']:
            return 38
        
        raise ValueError("Provided genome assembly not known: " + assemblyID)

    def getMafDbName(self):
        assemblyID = self.get("genomeAssembly")

        if assemblyID in ['hg19', 'hs37d5']:
            return "MafDb.gnomAD.r2.1.hs37d5"
        if assemblyID in ['hg38', 'GRCh38']:
            return "MafDb.gnomAD.r2.1.GRCh38"

        raise ValueError("Provided genome assembly not known: " + assemblyID)
 
    def getTempSampleParams(self):
        return(self.tempSampleParams)

    # if mae still defines genome. Use that and print warning. otherwise use globally defined genome
    def getGenomeFiles(self):
        try:
            fastaFiles = self.get("mae")["genome"]
            logger.info( \
"WARNING: Using the mae defined genome instead of the globally defined one.\n\
This will be depreciated in the future to allow for reference genomes to be defined in \
the sample annotation table. Please update your config and SA table\n")
        
        except:
            fastaFiles = self.get("genome")
        return fastaFiles

    # generate name for genome dict based on fastaFile
    def getGenomeDict(self,fastaFile):
        return Path(fastaFile).with_suffix(".dict")

