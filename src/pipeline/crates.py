from src.pipeline.models import PackageManager
from src.pipeline.utils.fetcher import TarballFetcher
from src.pipeline.utils.logger import Logger
from src.pipeline.utils.pg import DB
from src.pipeline.utils.transformer import CratesTransformer

FILE_LOCATION = "https://static.crates.io/db-dump.tar.gz"

logger = Logger("crates_orchestrator", mode=Logger.VERBOSE)


def get_crates_packages(db: DB) -> None:
    # get crates's package manager id, and add it if it doesn't exist
    package_manager_id = db.get_package_manager_id("crates")
    if package_manager_id is None:
        package_manager_id = db.insert_package_manager("crates")
    package_manager = PackageManager(id=package_manager_id, name="crates")

    # use the fetcher to get the fileis from crates itself
    logger.log("need to unravel a ~3GB tarball, this takes ~42 seconds")
    fetcher = TarballFetcher("crates", FILE_LOCATION)
    files = fetcher.fetch()
    fetcher.write(files)

    # use the transformer to figure out what we'd need for our ranker
    transformer = CratesTransformer()
    logger.log("transforming crates packages")

    # load the projects, versions, and dependencies into our db
    logger.log("loading crates packages into db, currently this might take a while")

    # TODO: handle auto-generated ids
    # auto-generated ids are something this orchestrator does not know about
    # I don't wanna get them, I'd rather just collect the ids when I load packages
    # and then use those ids to insert the versions
    # ughhhh, this is not the best way to do this, but it works for now

    # packages
    db.insert_packages(transformer.packages(), package_manager)

    # update the transformer's map with all the db_ids
    logger.log("getting loaded pkg_ids to correctly load versions (takes 5 seconds)")
    loaded_packages = db.select_packages_by_package_manager(package_manager)
    transformer.update_crates_db_ids(loaded_packages)

    # versions
    db.insert_versions(transformer.versions())

    # update the transformer's map with all the db_ids
    logger.log("getting loaded ver_ids to correctly load deps (takes 50 seconds)")
    loaded_versions = db.select_versions_by_package_manager(package_manager)
    transformer.update_crates_versions_db_ids(loaded_versions)

    # dependencies
    logger.log("loading crates dependencies into db...this will take the longest")
    db.insert_dependencies(transformer.dependencies())

    # insert load history
    db.insert_load_history(package_manager_id)
    logger.log("✅ crates")
    logger.log("in a new terminal, run README.md/db-list-history to verify")
