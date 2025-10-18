# Copyright (c) Microsoft. All rights reserved.

"""Spam Detection Workflow Sample for DevUI.

The following sample demonstrates a comprehensive 5-step workflow with multiple executors
that process, analyze, detect spam, and handle email messages. This workflow illustrates
complex branching logic and realistic processing delays to demonstrate the workflow framework.

Workflow Steps:
1. Email Preprocessor - Cleans and prepares the email
2. Content Analyzer - Analyzes email content and structure
3. Spam Detector - Determines if the message is spam
4a. Spam Handler - Processes spam messages (quarantine, log, remove)
4b. Message Responder - Handles legitimate messages (validate, respond)
5. Final Processor - Completes the workflow with logging and cleanup
"""

import asyncio
from email.mime import image
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
import mimetypes
from dotenv import load_dotenv

from agent_framework import (
    Case,
    ChatMessage,
    Default,
    Executor,
    TextContent,
    UriContent,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)
from agent_framework.openai import OpenAIResponsesClient

from pydantic import BaseModel, Field
from typing_extensions import Never

import os
from pathlib import Path
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, PublicAccess, ContentSettings
from azure.core.exceptions import ResourceExistsError


@dataclass
class WorkflowContent:
    """A data class to hold the processed email content."""

    original_message: str
    input_path: str
    is_image: bool
    cleaned_message: str
    word_count: int
    has_suspicious_patterns: bool = False



@dataclass
class ContentAnalysis:
    """A data class to hold content analysis results."""

    email_content: WorkflowContent
    sentiment_score: float
    contains_links: bool
    has_attachments: bool
    risk_indicators: list[str]


@dataclass
class SpamDetectorResponse:
    """A data class to hold the spam detection results."""

    analysis: ContentAnalysis
    is_spam: bool = False
    confidence_score: float = 0.0
    spam_reasons: list[str] | None = None

    def __post_init__(self):
        """Initialize spam_reasons list if None."""
        if self.spam_reasons is None:
            self.spam_reasons = []


@dataclass
class ProcessingResult:
    """A data class to hold the final processing result."""

    original_message: str
    action_taken: str
    processing_time: float
    status: str
    is_spam: bool
    confidence_score: float
    spam_reasons: list[str]
    input_path: str
    is_image: bool


@dataclass
class BlobUploadResult:
    """A data class to hold blob upload results."""

    blob_url: str
    blob_name: str
    container_name: str
    content_type: str
    upload_timestamp: str
    file_size_bytes: int
    original_path: str





class WorkflowRequest(BaseModel):
    """Request model for email processing."""

    path: str = Field(
        description="The file path to be processed",
        default="test_image_01.png",
    )


class InputPreprocessor(Executor):
    """Step 1: An executor that preprocesses input content"""

    @handler
    async def handle_workflow_request(self, workflowRequest: WorkflowRequest, ctx: WorkflowContext[WorkflowContent]) -> None:
        """Preprocess the workflow request"""
        logging.info(f"InputPreprocessor: Processing request")
        logging.debug(f"  Path: {workflowRequest.path}")
        
        await asyncio.sleep(1.5)  # Simulate preprocessing time

        # Check if file exists and is a common image type
        
        file_path = Path(workflowRequest.path)
        is_image = False
        
        if file_path.exists() and file_path.is_file():
            # Check for common image extensions
            common_image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff', '.tif'}
            is_image = file_path.suffix.lower() in common_image_extensions
            logging.info(f"  File exists: {file_path}")
            logging.info(f"  Extension: {file_path.suffix}")
            logging.info(f"  Is image: {is_image}")
        else:
            # File doesn't exist or is not a file
            logging.warning(f"  File not found or not a file: {file_path}")
            await ctx.send_message(WorkflowContent(
                original_message=workflowRequest.path,
                cleaned_message="",
                word_count=0,
                has_suspicious_patterns=False,
                input_path=workflowRequest.path,
                is_image=False,
            ))
            return
        
        # Simulate email cleaning
        cleaned = workflowRequest.path.strip().lower()
        word_count = len(workflowRequest.path.split())

        # Check for suspicious patterns
        suspicious_patterns = ["urgent", "limited time", "act now", "free money"]
        has_suspicious = any(pattern in cleaned for pattern in suspicious_patterns)

        result = WorkflowContent(
            original_message=cleaned,
            cleaned_message=cleaned,
            word_count=word_count,
            has_suspicious_patterns=has_suspicious,
            is_image=is_image,
            input_path=workflowRequest.path
        )

        await ctx.send_message(result)


class ContentAnalyzer(Executor):
    """Step 2: An executor that analyzes email content and structure."""

    @handler
    async def handle_email_content(self, email_content: WorkflowContent, ctx: WorkflowContext[ContentAnalysis]) -> None:
        """Analyze the email content for various indicators."""
        await asyncio.sleep(2.0)  # Simulate analysis time

        # Simulate content analysis
        sentiment_score = 0.5 if email_content.has_suspicious_patterns else 0.8
        contains_links = "http" in email_content.cleaned_message or "www" in email_content.cleaned_message
        has_attachments = "attachment" in email_content.cleaned_message

        # Build risk indicators
        risk_indicators: list[str] = []
        if email_content.has_suspicious_patterns:
            risk_indicators.append("suspicious_language")
        if contains_links:
            risk_indicators.append("contains_links")
        if has_attachments:
            risk_indicators.append("has_attachments")
        if email_content.word_count < 10:
            risk_indicators.append("too_short")

        analysis = ContentAnalysis(
            email_content=email_content,
            sentiment_score=sentiment_score,
            contains_links=contains_links,
            has_attachments=has_attachments,
            risk_indicators=risk_indicators,
        )

        await ctx.send_message(analysis)


class SpamDetector(Executor):
    """Step 3: An executor that determines if a message is spam based on analysis."""

    def __init__(self, spam_keywords: list[str], id: str):
        """Initialize the executor with spam keywords."""
        super().__init__(id=id)
        self._spam_keywords = spam_keywords

    @handler
    async def handle_analysis(self, analysis: ContentAnalysis, ctx: WorkflowContext[SpamDetectorResponse]) -> None:
        """Determine if the message is spam based on content analysis."""
        await asyncio.sleep(1.8)  # Simulate detection time

        # Check for spam keywords
        email_text = analysis.email_content.cleaned_message
        keyword_matches = [kw for kw in self._spam_keywords if kw in email_text]

        # Calculate spam probability
        spam_score = 0.0
        spam_reasons: list[str] = []

        if keyword_matches:
            spam_score += 0.4
            spam_reasons.append(f"spam_keywords: {keyword_matches}")

        if analysis.email_content.has_suspicious_patterns:
            spam_score += 0.3
            spam_reasons.append("suspicious_patterns")

        if len(analysis.risk_indicators) >= 3:
            spam_score += 0.2
            spam_reasons.append("high_risk_indicators")

        if analysis.sentiment_score < 0.4:
            spam_score += 0.1
            spam_reasons.append("negative_sentiment")

        is_spam = spam_score >= 0.5

        result = SpamDetectorResponse(
            analysis=analysis, is_spam=is_spam, confidence_score=spam_score, spam_reasons=spam_reasons
        )

        await ctx.send_message(result)


class SpamHandler(Executor):
    """Step 4a: An executor that handles spam messages with quarantine and logging."""

    @handler
    async def handle_spam_detection(
        self,
        spam_result: SpamDetectorResponse,
        ctx: WorkflowContext[ProcessingResult],
    ) -> None:
        """Handle spam messages by quarantining and logging."""
        if not spam_result.is_spam:
            raise RuntimeError("Message is not spam, cannot process with spam handler.")

        await asyncio.sleep(2.2)  # Simulate spam handling time

        result = ProcessingResult(
            original_message=spam_result.analysis.email_content.original_message,
            action_taken="quarantined_and_logged",
            processing_time=2.2,
            status="spam_handled",
            is_spam=spam_result.is_spam,
            confidence_score=spam_result.confidence_score,
            spam_reasons=spam_result.spam_reasons or [],
        )

        await ctx.send_message(result)


class MessageResponder(Executor):
    """Step 4b: An executor that responds to legitimate messages."""

    @handler
    async def handle_spam_detection(
        self,
        spam_result: SpamDetectorResponse,
        ctx: WorkflowContext[ProcessingResult],
    ) -> None:
        """Respond to legitimate messages."""
        if spam_result.is_spam:
            raise RuntimeError("Message is spam, cannot respond with message responder.")

        await asyncio.sleep(2.5)  # Simulate response time

        result = ProcessingResult(
            original_message=spam_result.analysis.email_content.original_message,
            action_taken="responded_and_filed",
            processing_time=2.5,
            status="message_processed",
            is_spam=spam_result.is_spam,
            confidence_score=spam_result.confidence_score,
            spam_reasons=spam_result.spam_reasons or [],
        )

        await ctx.send_message(result)


class FinalProcessor(Executor):
    """Step 5: An executor that completes the workflow with final logging and cleanup."""

    @handler
    async def handle_processing_result(
        self,
        result: ProcessingResult,
        ctx: WorkflowContext[Never, str],
    ) -> None:
        """Complete the workflow with final processing and logging."""
        await asyncio.sleep(1.5)  # Simulate final processing time

        total_time = result.processing_time + 1.5

        # Include classification details in completion message
        classification = "SPAM" if result.is_spam else "LEGITIMATE"
        reasons = ", ".join(result.spam_reasons) if result.spam_reasons else "none"

        completion_message = (
            f"Email classified as {classification} (confidence: {result.confidence_score:.2f}). "
            f"Reasons: {reasons}. "
            f"Action: {result.action_taken}, "
            f"Status: {result.status}, "
            f"Total time: {total_time:.1f}s"
        )

        await ctx.yield_output(completion_message)


class BlobStorageUploader(Executor):
    """An executor that uploads images to Azure Blob Storage with public access."""

    def __init__(self, id: str, connection_string: str | None = None, container_name: str = "images"):
        """Initialize the executor with Azure Blob Storage settings.
        
        Args:
            id: Executor ID
            connection_string: Azure Storage connection string (if None, uses env var AZURE_STORAGE_CONNECTION_STRING)
            container_name: Name of the blob container (default: "images")
        """
        super().__init__(id=id)
        load_dotenv()
        self._connection_string = connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self._container_name = container_name
        
        if not self._connection_string:
            raise ValueError(
                "Azure Storage connection string not provided. "
                "Set AZURE_STORAGE_CONNECTION_STRING environment variable or pass connection_string parameter."
            )

    @handler
    async def handle_email_content(
        self, 
        email_content: WorkflowContent, 
        ctx: WorkflowContext[BlobUploadResult]
    ) -> None:
        """Upload the image to Azure Blob Storage and return the public URL."""
        
        logging.info(f"BlobStorageUploader: Starting upload process")
        logging.debug(f"  Input path: {email_content.input_path}")
        logging.debug(f"  Is image: {email_content.is_image}")
        
        if not email_content.is_image:
            raise RuntimeError("Content is not an image, cannot upload to blob storage.")
        
        input_path = Path(email_content.input_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Image file not found: {input_path}")
        
        logging.info(f"  File exists: {input_path} ({input_path.stat().st_size} bytes)")
        
        # Create BlobServiceClient
        logging.debug(f"  Creating BlobServiceClient...")
        blob_service_client = BlobServiceClient.from_connection_string(self._connection_string)
        logging.debug(f"  BlobServiceClient created successfully")
        
        # Get or create container with public access for blobs
        container_client = blob_service_client.get_container_client(self._container_name)
        logging.debug(f"  Container client obtained for '{self._container_name}'")
        
        # Check if container exists, create if it doesn't
        try:
            # Try to get container properties to check if it exists
            logging.debug(f"  Checking if container exists...")
            container_client.get_container_properties()
            logging.info(f"  Using existing container '{self._container_name}'")
        except Exception as e:
            # Container doesn't exist, create it
            logging.info(f"  Container '{self._container_name}' not found, creating it...")
            logging.debug(f"  Exception: {e}")
            try:
                container_client.create_container(public_access=PublicAccess.Blob)
                logging.info(f"  Created container '{self._container_name}' with public blob access")
            except ResourceExistsError:
                # Race condition - container was created between check and create
                logging.info(f"  Container '{self._container_name}' already exists")
            except Exception as create_error:
                logging.error(f"  Failed to create container: {create_error}")
                raise
        
        # Generate unique blob name with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        blob_name = f"{timestamp}_{input_path.name}"
        logging.info(f"  Generated blob name: {blob_name}")
        
        # Get content type
        content_type, _ = mimetypes.guess_type(str(input_path))
        if not content_type:
            content_type = "application/octet-stream"
        logging.debug(f"  Content type: {content_type}")
        
        # Upload the file
        blob_client = container_client.get_blob_client(blob_name)
        logging.debug(f"  Blob client obtained for '{blob_name}'")
        
        file_size = input_path.stat().st_size
        logging.info(f"  Uploading {file_size:,} bytes...")
        
        with open(input_path, "rb") as data:
            blob_client.upload_blob(
                data, 
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )
        
        # Get the public URL
        blob_url = blob_client.url
        
        logging.info(f"✓ Successfully uploaded {input_path.name} to Azure Blob Storage")
        logging.info(f"  Public URL: {blob_url}")
        
        result = BlobUploadResult(
            blob_url=blob_url,
            blob_name=blob_name,
            container_name=self._container_name,
            content_type=content_type,
            upload_timestamp=datetime.now(timezone.utc).isoformat(),
            file_size_bytes=file_size,
            original_path=str(input_path)
        )
        
        await ctx.send_message(result)


class ImageAnalyzer(Executor):
    """An executor that analyzes images using OpenAI."""

    def __init__(self, id: str):
        """Initialize the executor with an OpenAI agent."""
        super().__init__(id=id)
        self._agent = OpenAIResponsesClient().create_agent(
            name="Image Analyzer Agent",
            instructions="You are a helpful agent that can analyze images and extract relevant information.",
        )

    @handler
    async def handle_blob_upload(self, blob_result: BlobUploadResult, ctx: WorkflowContext[ContentAnalysis]) -> None:
        """Analyze the uploaded image using its public blob URL."""
        
        # Create a message with the image from blob storage
        user_message = ChatMessage(
            role="user",
            contents=[
                TextContent(text="Please analyze this image and extract relevant information."),
                UriContent(
                    uri=blob_result.blob_url,
                    media_type=blob_result.content_type,
                ),
            ],
        )
        
        # Get the agent's response
        response = await self._agent.run(user_message)
        
        logging.info(f"Image analysis complete for {blob_result.blob_name}")
        logging.info(f"Agent response: {response}")
        
        # Create analysis based on agent response
        # For now, create a placeholder analysis
        # You can enhance this to parse the agent's response
        analysis = ContentAnalysis(
            email_content=WorkflowContent(
                original_message=blob_result.blob_url,
                input_path=blob_result.original_path,
                is_image=True,
                cleaned_message=f"Image analyzed from blob: {blob_result.blob_url}",
                word_count=0,
                has_suspicious_patterns=False,
            ),
            sentiment_score=0.8,
            contains_links=False,
            has_attachments=True,
            risk_indicators=["image_content"],
        )

        await ctx.send_message(analysis)

    @handler
    async def handle_email_content(self, email_content: WorkflowContent, ctx: WorkflowContext[ContentAnalysis]) -> None:
        """Analyze the image content using local file path (fallback)."""
        
        input_path = email_content.original_message
        
        # Create a message with the image
        user_message = ChatMessage(
            role="user",
            contents=[
                TextContent(text="Please analyze this image and extract relevant information."),
                UriContent(
                    uri="https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                    media_type="image/jpeg",
                ),
            ],
        )
        
        # Get the agent's response
        response = await self._agent.run(user_message)
        
        # Create a placeholder analysis
        analysis = ContentAnalysis(
            email_content=email_content,
            sentiment_score=0.5,
            contains_links=False,
            has_attachments=False,
            risk_indicators=["image_content"],
        )

        await ctx.send_message(analysis)


# Create the workflow instance that DevUI can discover
spam_keywords = ["spam", "advertisement", "offer", "click here", "winner", "congratulations", "urgent"]

# Create all the executors for the 5-step workflow
input_preprocessor = InputPreprocessor(id="input_preprocessor")
content_analyzer = ContentAnalyzer(id="content_analyzer")
spam_detector = SpamDetector(spam_keywords, id="spam_detector")
spam_handler = SpamHandler(id="spam_handler")
message_responder = MessageResponder(id="message_responder")
final_processor = FinalProcessor(id="final_processor")

# Image processing executors
blob_uploader = BlobStorageUploader(id="blob_uploader", container_name="images")
image_analyzer = ImageAnalyzer(id="image_analyzer")

# Build the comprehensive 5-step workflow with branching logic
workflow = (
    WorkflowBuilder(
        name="Workflow Workflow",
        description="Workflow to create Agent Framework workflows with Azure Blob Storage image upload",
    )
    .set_start_executor(input_preprocessor)
    .add_switch_case_edge_group(
        input_preprocessor,
        [
            Case(condition=lambda x: x.is_image, target=blob_uploader),
            Default(target=content_analyzer),
        ],
    )
    .add_edge(blob_uploader, image_analyzer)
    .add_edge(image_analyzer, spam_detector)
    .add_edge(content_analyzer, spam_detector)
    .add_switch_case_edge_group(
        spam_detector,
        [
            Case(condition=lambda x: x.is_spam, target=spam_handler),
            Default(target=message_responder),
        ],
    )
    .add_edge(spam_handler, final_processor)
    .add_edge(message_responder, final_processor)
    .build()
)

# Note: Workflow metadata is determined by executors and graph structure


def main():
    """Launch the spam detection workflow in DevUI."""
    from agent_framework.devui import serve

    # Setup detailed logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger(__name__)

    logger.info("="*60)
    logger.info("Starting Workflow Workflow with Azure Blob Storage")
    logger.info("="*60)
    logger.info("Available at: http://localhost:8090")
    logger.info("Entity ID: workflow_spam_detection")
    logger.info("="*60)

    # Launch server with the workflow
    serve(entities=[workflow], port=8090, auto_open=True)


if __name__ == "__main__":
    main()