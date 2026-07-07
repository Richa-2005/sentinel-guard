import csv
import re
from pathlib import Path

class KnowledgeBaseManager:
    """Load and normalize the documents used by the compliance knowledge base."""

    def __init__(self, data_directory: str | Path | None = None):
        if data_directory is None:
            data_directory = Path(__file__).resolve().parents[2] / "data"

        data_path = Path(data_directory)
        self.master_data_collection: list[str] = []

        self.corp_policy = (data_path / "corporate_policy.txt").read_text(
            encoding="utf-8"
        )
        self.network_tos = (data_path / "network_tos.txt").read_text(
            encoding="utf-8"
        )
        self.rbi_circular = (data_path / "rbi_circular.txt").read_text(
            encoding="utf-8"
        )

        self._load_text_file(self.corp_policy)
        self._load_text_file(self.network_tos)
        self._load_text_file(self.rbi_circular)

        self.mcc_codes_file = data_path / "mcc_codes.csv"
        self.mcc_registry: dict[str, dict[str, str]] = {}
        self._load_mcc_registry()

    def _load_text_file(self, file_data: str) -> list[str]:
        """
        Clean, split, and add text content to the master collection.
        """
        if not isinstance(file_data, str):
            raise TypeError("file_data must be a string")

        # Normalize line endings and remove whitespace at the end of every line.
        cleaned_text = file_data.replace("\r\n", "\n").replace("\r", "\n")
        cleaned_text = "\n".join(line.rstrip() for line in cleaned_text.split("\n"))

        # The source documents use long runs of hyphens around section headers.
        cleaned_text = re.sub(r"(?m)^\s*-{3,}\s*$", "", cleaned_text)

        # Lookaheads retain the header at the beginning of its resulting chunk.
        header_boundary = re.compile(
            r"(?m)(?=^(?:SECTION\s+\d+\s*:|\d+\.\d+(?:\s+|$)))",
            flags=re.IGNORECASE,
        )
        chunks = [chunk.strip() for chunk in header_boundary.split(cleaned_text)]
        chunks = [chunk for chunk in chunks if chunk]

        self.master_data_collection.extend(chunks)
        return chunks

    def _load_mcc_registry(self) -> None:
        with self.mcc_codes_file.open(mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            required_headers = {"mcc_code", "category", "risk_level"}
            if not reader.fieldnames or not required_headers.issubset(reader.fieldnames):
                raise ValueError(
                    "MCC registry must contain mcc_code, category, and risk_level columns"
                )

            for row in reader:
                mcc_code = row["mcc_code"].strip()
                if not mcc_code:
                    continue
                self.mcc_registry[mcc_code] = {
                    "category": row["category"].strip(),
                    "risk_level": row["risk_level"].strip(),
                }

    def query_relevant_context(self, transaction_data: dict, hydrated_metrics: dict) -> str:
        """
        Dynamically cross-reference metrics and search keywords across the text corpus
        to return isolated regulatory context blocks matching active threat profiles.
        """
        # 1. Initialize a collection set to gather unique matching context chunks
        matched_chunks: list[str] = []
        search_keywords: set[str] = set()

        # 2. Extract and scan the Merchant Category Code (MCC)
        merchant_id = str(transaction_data.get("merchant_id", "")).strip()
        if merchant_id in self.mcc_registry:
            mcc_info = self.mcc_registry[merchant_id]
            category = mcc_info["category"]
            risk_level = mcc_info["risk_level"]
            
            # Form an initial explicit context anchor from our O(1) registry map
            mcc_context_string = (
                f"INTEL: Inbound Merchant Category Code (MCC) [{merchant_id}] maps "
                f"directly to the sector '{category}' with an assigned risk severity profile of: {risk_level}."
            )
            matched_chunks.append(mcc_context_string)
            
            # Add keywords dynamically based on the merchant category profile
            search_keywords.add(category.lower())
            search_keywords.add(risk_level.lower())

        # 3. Access Hydrated Metrics and Map to Compliance Keywords
        # Check if the device card tracking threshold limits were crossed
        if float(hydrated_metrics.get("device_card_limit_crossed", 0.0)) == 1.0:
            search_keywords.update(["device", "multiplex", "hardware", "ring"])

        # Check if short-term rolling velocity restrictions are breached
        if int(hydrated_metrics.get("card_vel_10m", 0)) > 3:
            search_keywords.update(["velocity", "window", "consecutive", "testing"])

        # Check if transaction magnitude crosses corporate spending ceilings
        if int(transaction_data.get("amount_paise", 0)) >= 25000:
            search_keywords.update(["ceiling", "cap", "magnitude", "authorized"])

        # Check if the transaction landed in the high-risk off-hours window
        if float(hydrated_metrics.get("is_off_hours_window", 0.0)) == 1.0:
            search_keywords.update(["off-hours", "temporal", "boundary", "window"])

        # 4. Comb the Master Text Corpus chunks for keyword intersections
        for chunk in self.master_data_collection:
            chunk_lower = chunk.lower()
            # If any activated keyword hits this segment, extract it for the LLM prompt context
            if any(keyword in chunk_lower for keyword in search_keywords):
                if chunk not in matched_chunks:
                    matched_chunks.append(chunk)

        # 5. Fallback check: If no anomalies hit, load standard base compliance intros
        if not matched_chunks:
            for chunk in self.master_data_collection:
                if "introduction" in chunk.lower() or "objective" in chunk.lower():
                    matched_chunks.append(chunk)

        # Return a unified double-line-broken string corpus block
        return "\n\n".join(matched_chunks)
            
        