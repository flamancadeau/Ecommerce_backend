from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from .models import Product
from .models import Category
from .models import Variant
from .serializers import VariantSerializer
from .serializers import CategorySerializer
from .serializers import ProductSerializer
from rest_framework import serializers

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new product with custom response."""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(
                {
                    'success': True,
                    'message': 'Product created successfully!',
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to create product.',
                    'errors': e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """List all products with success message."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                'success': True,
                'message': 'Products retrieved successfully!',
                'data': serializer.data,
                'count': len(serializer.data)
            },
            status=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single product by ID with custom response."""
        try:
            product = self.get_object()
            serializer = self.get_serializer(product)
            return Response(
                {
                    'success': True,
                    'message': 'Product retrieved successfully!',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except NotFound:
            return Response(
                {
                    'success': False,
                    'message': 'Product not found.',
                    'errors': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        """Update a product by ID with custom response."""
        try:
            product = self.get_object()
            serializer = self.get_serializer(product, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(
                {
                    'success': True,
                    'message': 'Product updated successfully!',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except serializers.ValidationError as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to update product.',
                    'errors': e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except NotFound:
            return Response(
                {
                    'success': False,
                    'message': 'Product not found.',
                    'errors': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        """Delete a product by ID with custom response."""
        try:
            product = self.get_object()
            self.perform_destroy(product)
            return Response(
                {
                    'success': True,
                    'message': 'Product deleted successfully!',
                    'data': None
                },
                status=status.HTTP_204_NO_CONTENT
            )
        except NotFound:
            return Response(
                {
                    'success': False,
                    'message': 'Product not found.',
                    'errors': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def create(self, request, *args, **kwargs):
        """Create a new category with custom response."""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(
                {
                    'success': True,
                    'message': 'Category created successfully!',
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to create category.',
                    'errors': e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """List all categories with success message."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                'success': True,
                'message': 'Categories retrieved successfully!',
                'data': serializer.data,
                'count': len(serializer.data)
            },
            status=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single category by ID with custom response."""
        try:
            category = self.get_object()
            serializer = self.get_serializer(category)
            return Response(
                {
                    'success': True,
                    'message': 'Category retrieved successfully!',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except NotFound:
            return Response(
                {
                    'success': False,
                    'message': 'Category not found.',
                    'errors': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        """Update a category by ID with custom response."""
        try:
            category = self.get_object()
            serializer = self.get_serializer(category, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(
                {
                    'success': True,
                    'message': 'Category updated successfully!',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except serializers.ValidationError as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to update category.',
                    'errors': e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except NotFound:
            return Response(
                {
                    'success': False,
                    'message': 'Category not found.',
                    'errors': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        """Delete a category by ID with custom response."""
        try:
            category = self.get_object()
            self.perform_destroy(category)
            return Response(
                {
                    'success': True,
                    'message': 'Category deleted successfully!',
                    'data': None
                },
                status=status.HTTP_204_NO_CONTENT
            )
        except NotFound:
            return Response(
                {
                    'success': False,
                    'message': 'Category not found.',
                    'errors': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VariantViewSet(viewsets.ModelViewSet):
    queryset = Variant.objects.all()
    serializer_class = VariantSerializer

    def create(self, request, *args, **kwargs):
        """Create a new variant with custom response."""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(
                {
                    'success': True,
                    'message': 'Variant created successfully!',
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to create variant.',
                    'errors': e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def list(self, request, *args, **kwargs):
        """List all variants with success message."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                'success': True,
                'message': 'Variants retrieved successfully!',
                'data': serializer.data,
                'count': len(serializer.data)
            },
            status=status.HTTP_200_OK
        )

    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single variant by ID with custom response."""
        try:
            variant = self.get_object()
            serializer = self.get_serializer(variant)
            return Response(
                {
                    'success': True,
                    'message': 'Variant retrieved successfully!',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except NotFound:
            return Response(
                {
                    'success': False,
                    'message': 'Variant not found.',
                    'errors': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        """Update a variant by ID with custom response."""
        try:
            variant = self.get_object()
            serializer = self.get_serializer(variant, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(
                {
                    'success': True,
                    'message': 'Variant updated successfully!',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except serializers.ValidationError as e:
            return Response(
                {
                    'success': False,
                    'message': 'Failed to update variant.',
                    'errors': e.detail
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except NotFound:
            return Response(
                {
                    'success': False,
                    'message': 'Variant not found.',
                    'errors': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        """Delete a variant by ID with custom response."""
        try:
            variant = self.get_object()
            self.perform_destroy(variant)
            return Response(
                {
                    'success': True,
                    'message': 'Variant deleted successfully!',
                    'data': None
                },
                status=status.HTTP_204_NO_CONTENT
            )
        except NotFound:
            return Response(
                {
                    'success': False,
                    'message': 'Variant not found.',
                    'errors': None
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'An error occurred: {str(e)}',
                    'errors': None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
