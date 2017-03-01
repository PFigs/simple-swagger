import codecs
import jinja2
import logging
import yaml

from swagger_spec_validator.validator20 import validate_spec

class SwaggerParser(object):
    """Parse a swagger YAML file.
    Get definitions examples, routes default data, and routes validator.
    This only works with swagger 2.0.
    Attributes:
        specification: dict of the yaml file.
        definitions_example: dict of definition with an example.
        paths: dict of path with their actions, parameters, and responses.
    """

    _HTTP_VERBS = set(['get', 'put', 'post', 'delete', 'options', 'head', 'patch'])

    def __init__(self, swagger_path):
        """Run parsing from either a file or a dict.
        Args:
            swagger_path: path of the swagger file.
            swagger_dict: swagger dict.
            use_example: Define if we use the example from the YAML when we
                         build definitions example (False value can be useful
                         when making test. Problem can happen if set to True, eg
                         POST {'id': 'example'}, GET /string => 404).
        Raises:
            - ValueError: if no swagger_path or swagger_dict is specified.
                          Or if the given swagger is not valid.
        """
        try:
            if swagger_path is not None:
                # Open yaml file
                arguments = {}
                with codecs.open(swagger_path, 'r', 'utf-8') as swagger_yaml:
                    swagger_template = swagger_yaml.read()
                    swagger_string = jinja2.Template(swagger_template).render(**arguments)
                    self.specification = yaml.load(swagger_string)
            else:
                raise ValueError('You must specify a swagger_path or dict')
            validate_spec(self.specification, '')
        except Exception as e:
            raise ValueError('{0} is not a valid swagger2.0 file: {1}'.format(swagger_path,  e))

        # Run parsing
        self.host = self.specification.get('host')
        self.base_path = self.specification.get('basePath', '')
        self.schemes = self.specification.get('host')

        self.paths = {}
        self.operation = {}
        
        self.__get_paths_data()


    def __getattr__(self, key):
        try:
            return self.operation[key]
        except KeyError as e:
            raise AttributeError(e)


    def __get_paths_data(self):
        """Get data for each paths in the swagger specification.
        Get also the list of operationId.
        """
        for path, path_spec in self.specification['paths'].items():
            path = u'{0}{1}'.format(self.base_path, path)
            self.paths[path] = {}

            # Add path-level parameters
            default_parameters = {}
            if 'parameters' in path_spec:
                self._add_parameters(default_parameters, path_spec['parameters'])

            for http_method in path_spec.keys():
                if http_method not in self._HTTP_VERBS:
                    logging.getLogger(__name__)

                self.paths[path][http_method] = {}

                # Add to operation list
                action = path_spec[http_method]
                tag = action['tags'][0] if 'tags' in action.keys() and action['tags'] else None
                if 'operationId' in action.keys():
                    self.operation[action['operationId']] = (path, http_method, tag)

                # Get parameters
                self.paths[path][http_method]['parameters'] = default_parameters.copy()
                if 'parameters' in action.keys():
                    self._add_parameters(self.paths[path][http_method]['parameters'], action['parameters'])

                # Get responses
                self.paths[path][http_method]['responses'] = action['responses']

                # Get mime types for this action
                if 'consumes' in action.keys():
                    self.paths[path][http_method]['consumes'] = action['consumes']

    def _add_parameters(self, parameter_map, parameter_list):
        """Populates the given parameter map with the list of parameters provided, resolving any reference objects encountered.
        Args:
            parameter_map: mapping from parameter names to parameter objects
            parameter_list: list of either parameter objects or reference objects
        """
        for parameter in parameter_list:
            if parameter.get('$ref'):
                # expand parameter from $ref if not specified inline
                parameter = self.specification['parameters'].get(parameter.get('$ref').split('/')[-1])
            parameter_map[parameter['name']] = parameter

   