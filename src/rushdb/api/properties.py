import typing
from typing import List, Optional

from ..models.property import Property, PropertyValuesData
from ..models.search_query import SearchQuery
from ..models.transaction import Transaction
from .base import BaseAPI


class PropertyValuesQuery(SearchQuery, total=False):
    """Extended SearchQuery for property values endpoint with text search support.

    This class extends the base SearchQuery to include additional search capabilities
    specifically for querying property values, including text-based search functionality.

    Attributes:
        query (Optional[str]): Text search string to filter property values.
            When provided, performs a text-based search among the property values.
    """

    query: Optional[str]  # For text search among values


class PropertiesAPI(BaseAPI):
    """API client for managing properties in RushDB.

    The PropertiesAPI provides functionality for working with database properties,
    including searching for properties, retrieving individual properties by ID,
    deleting properties, and querying property values. Properties represent
    metadata about the structure and characteristics of data in the database.

    This class handles:
    - Property discovery and searching
    - Individual property retrieval
    - Property deletion
    - Property values querying with text search capabilities
    - Transaction support for all operations

    Attributes:
        client: The underlying RushDB client instance for making HTTP requests.

    Example:
        >>> from rushdb import RushDB
        >>> client = RushDB(api_key="your_api_key")
        >>> properties_api = client.properties
        >>>
        >>> # Find all properties
        >>> properties = properties_api.find()
        >>>
        >>> # Get a specific property
        >>> property_obj = properties_api.find_by_id("property_123")
    """

    def find(
        self,
        search_query: Optional[SearchQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[Property]:
        """Search for and retrieve properties matching the specified criteria.

        Searches the database for properties that match the provided search query.
        Properties represent metadata about the database structure and can be
        filtered using various search criteria.

        Args:
            search_query (Optional[SearchQuery], optional): The search criteria to filter properties.
                If None, returns all properties. Can include filters for property names,
                types, or other metadata. Defaults to None.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            List[Property]: List of Property objects matching the search criteria.

        Raises:
            RequestError: If the server request fails.

        Example:
            >>> from rushdb.models.search_query import SearchQuery
            >>> properties_api = PropertiesAPI(client)
            >>>
            >>> # Find all properties
            >>> all_properties = properties_api.find()
            >>>
            >>> # Find properties with specific criteria
            >>> query = SearchQuery(where={"age":{"$gte": 30}})
            >>> string_properties = properties_api.find(query)
        """
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "POST",
            "/properties/search",
            typing.cast(typing.Dict[str, typing.Any], search_query or {}),
            headers,
        )

    def find_by_id(
        self, property_id: str, transaction: Optional[Transaction] = None
    ) -> Property:
        """Retrieve a specific property by its unique identifier.

        Fetches a single property from the database using its unique ID.
        This method is useful when you know the exact property you want to retrieve.

        Args:
            property_id (str): The unique identifier of the property to retrieve.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            Property: The Property object with the specified ID.

        Raises:
            ValueError: If the property_id is invalid or empty.
            NotFoundError: If no property exists with the specified ID.
            RequestError: If the server request fails.

        Example:
            >>> properties_api = PropertiesAPI(client)
            >>> property_obj = properties_api.find_by_id("prop_123")
            >>> print(property_obj.name)
        """
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "GET", f"/properties/{property_id}", headers=headers
        )

    def delete(
        self, property_id: str, transaction: Optional[Transaction] = None
    ) -> None:
        """Delete a property from the database.

        Permanently removes a property and all its associated metadata from the database.
        This operation cannot be undone, so use with caution.

        Args:
            property_id (str): The unique identifier of the property to delete.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            None: This method does not return a value.

        Raises:
            ValueError: If the property_id is invalid or empty.
            NotFoundError: If no property exists with the specified ID.
            RequestError: If the server request fails.

        Warning:
            This operation permanently deletes the property and cannot be undone.
            Ensure you have proper backups and confirmation before deleting properties.

        Example:
            >>> properties_api = PropertiesAPI(client)
            >>> properties_api.delete("prop_123")
            >>> # Property is now permanently deleted
        """
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "DELETE", f"/properties/{property_id}", headers=headers
        )

    def values(
        self,
        property_id: str,
        search_query: Optional[PropertyValuesQuery] = None,
        transaction: Optional[Transaction] = None,
    ) -> PropertyValuesData:
        """Retrieve and search values data for a specific property.

        Gets statistical and analytical data about the values stored in a particular property,
        including value distributions, counts, and other metadata. Supports text-based
        searching within the property values.

        Args:
            property_id (str): The unique identifier of the property to analyze.
            search_query (Optional[PropertyValuesQuery], optional): Extended search query
                that supports text search among property values. Can include:
                - Standard SearchQuery filters
                - query (str): Text search string to filter values
                Defaults to None.
            transaction (Optional[Transaction], optional): Transaction context for the operation.
                If provided, the operation will be part of the transaction. Defaults to None.

        Returns:
            PropertyValuesData: Object containing statistical and analytical data about
                the property's values, including distributions, counts, and value samples.

        Raises:
            ValueError: If the property_id is invalid or empty.
            NotFoundError: If no property exists with the specified ID.
            RequestError: If the server request fails.

        Example:
            >>> properties_api = PropertiesAPI(client)
            >>>
            >>> # Get all values data for a property
            >>> values_data = properties_api.values("prop_123")
            >>> print(f"Total values: {values_data.total}")
            >>>
            >>> # Search for specific values
            >>> query = PropertyValuesQuery(query="search_text")
            >>> filtered_values = properties_api.values("prop_123", query)
        """
        headers = Transaction._build_transaction_header(transaction)

        return self.client._make_request(
            "POST",
            f"/properties/{property_id}/values",
            typing.cast(typing.Dict[str, typing.Any], search_query or {}),
            headers,
        )
