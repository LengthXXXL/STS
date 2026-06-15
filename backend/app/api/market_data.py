from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.market_data import (
    MarketDataCoverageResponse,
    MarketDataPrepareResponse,
    MarketDataRequest,
)
from app.services.market_data_download_service import (
    get_market_data_coverage,
    prepare_market_data,
)
from app.services.market_data_service import DefaultMarketDataProvider

router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.post("/coverage", response_model=MarketDataCoverageResponse)
def coverage(
    request: MarketDataRequest,
    db: Session = Depends(get_db),
) -> MarketDataCoverageResponse:
    return get_market_data_coverage(db, request)


@router.post("/prepare", response_model=MarketDataPrepareResponse)
def prepare(
    request: MarketDataRequest,
    db: Session = Depends(get_db),
) -> MarketDataPrepareResponse:
    return prepare_market_data(db, request, source_provider=DefaultMarketDataProvider())
