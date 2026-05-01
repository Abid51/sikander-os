"""
Self-Modification System for Igris AI
Allows AI to modify its own code based on user commands
"""

import json
import os
import inspect
import importlib
import ast
from datetime import datetime
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class SelfModificationSystem:
    def __init__(self):
        self.modification_history = []
        # backend/app/core/self_modification.py -> backend/
        self.system_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.modifications_log_file = os.path.join(self.system_root, "modifications.log")
        self.allowed_modules = [
            "app.core.ai_core",
            "app.core.ai_learning_systems",
            "app.core.content_generator",
            "app.api.routes",
            # Needed by SelfEvolutionEngine.forge_new_tool target.
            "app.system.os_control",
        ]
        self.blocked_tokens = [
            "os.system(",
            "subprocess.",
            "eval(",
            "exec(",
            "__import__(",
            "open(",
            "shutil.rmtree(",
        ]

    def modify_function(self, module_name: str, function_name: str, new_logic: str) -> Dict[str, Any]:
        """
        Modify AI system function based on user command
        
        Args:
            module_name: Python module to modify
            function_name: Function name to modify
            new_logic: New function implementation
            
        Returns:
            Status of modification
        """
        if module_name not in self.allowed_modules:
            return {
                "status": "error",
                "message": f"Module {module_name} is not allowed for modification",
                "error_code": "PERMISSION_DENIED"
            }
        validation = self._validate_code_snippet(new_logic, expected_function=function_name)
        if not validation["ok"]:
            return {
                "status": "error",
                "message": validation["message"],
                "error_code": "UNSAFE_CODE",
            }
        
        try:
            # Get module path
            module_path = os.path.join(
                self.system_root,
                module_name.replace(".", os.sep) + ".py"
            )
            
            if not os.path.exists(module_path):
                return {
                    "status": "error",
                    "message": f"Module file {module_path} not found",
                    "error_code": "MODULE_NOT_FOUND"
                }
            
            # Read current file
            with open(module_path, 'r') as f:
                current_content = f.read()
            
            # Create backup
            backup_path = module_path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            with open(backup_path, 'w') as f:
                f.write(current_content)
            
            # Inject new function code
            updated_content = self._inject_function(
                current_content,
                function_name,
                new_logic
            )
            if updated_content == current_content:
                return {
                    "status": "error",
                    "message": f"Function {function_name} not found in {module_name}",
                    "error_code": "FUNCTION_NOT_FOUND",
                }
            
            # Validate syntax
            try:
                compile(updated_content, module_path, 'exec')
            except SyntaxError as e:
                return {
                    "status": "error",
                    "message": f"Syntax error in new code: {str(e)}",
                    "error_code": "SYNTAX_ERROR",
                    "details": str(e)
                }
            
            # Write updated file
            with open(module_path, 'w') as f:
                f.write(updated_content)
            
            # Reload module
            try:
                importlib.reload(importlib.import_module(module_name))
            except Exception as reload_error:
                # Restore from backup
                with open(backup_path, 'r') as f:
                    f_content = f.read()
                with open(module_path, 'w') as f:
                    f.write(f_content)
                
                return {
                    "status": "error",
                    "message": f"Failed to reload module: {str(reload_error)}",
                    "error_code": "RELOAD_FAILED",
                    "details": str(reload_error)
                }
            
            # Log modification
            modification = {
                "timestamp": datetime.now().isoformat(),
                "module": module_name,
                "function": function_name,
                "backup_file": backup_path,
                "status": "success"
            }
            self.modification_history.append(modification)
            self._log_modification(modification)
            
            return {
                "status": "success",
                "message": f"Successfully modified {module_name}.{function_name}",
                "backup_file": backup_path,
                "modification_id": len(self.modification_history) - 1
            }
            
        except Exception as e:
            logger.error(f"Self-modification error: {str(e)}")
            return {
                "status": "error",
                "message": f"Modification failed: {str(e)}",
                "error_code": "MODIFICATION_FAILED",
                "details": str(e)
            }

    def modify_parameter(self, system_name: str, param_name: str, param_value: Any) -> Dict[str, Any]:
        """
        Modify AI system parameters/configuration
        
        Args:
            system_name: System to modify
            param_name: Parameter name
            param_value: New parameter value
            
        Returns:
            Status of modification
        """
        try:
            config_file = os.path.join(
                self.system_root,
                f"config_{system_name}.json"
            )
            
            # Load or create config
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # Create backup
            backup_path = config_file + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            with open(backup_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Update parameter
            old_value = config.get(param_name)
            config[param_name] = param_value
            
            # Save updated config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            modification = {
                "timestamp": datetime.now().isoformat(),
                "type": "parameter",
                "system": system_name,
                "parameter": param_name,
                "old_value": old_value,
                "new_value": param_value,
                "backup_file": backup_path,
                "status": "success"
            }
            self.modification_history.append(modification)
            self._log_modification(modification)
            
            return {
                "status": "success",
                "message": f"Successfully modified parameter {param_name} in {system_name}",
                "backup_file": backup_path
            }
            
        except Exception as e:
            logger.error(f"Parameter modification error: {str(e)}")
            return {
                "status": "error",
                "message": f"Parameter modification failed: {str(e)}",
                "error_code": "PARAM_MOD_FAILED"
            }

    def add_capability(self, module_name: str, capability_code: str) -> Dict[str, Any]:
        """
        Add new capability/function to AI system
        
        Args:
            module_name: Module to add capability to
            capability_code: New function/code to add
            
        Returns:
            Status of modification
        """
        if module_name not in self.allowed_modules:
            return {
                "status": "error",
                "message": f"Module {module_name} is not allowed for modification",
                "error_code": "PERMISSION_DENIED"
            }
        validation = self._validate_code_snippet(capability_code, expected_function=None)
        if not validation["ok"]:
            return {
                "status": "error",
                "message": validation["message"],
                "error_code": "UNSAFE_CODE",
            }
        
        try:
            module_path = os.path.join(
                self.system_root,
                module_name.replace(".", os.sep) + ".py"
            )
            
            if not os.path.exists(module_path):
                return {
                    "status": "error",
                    "message": f"Module file {module_path} not found",
                    "error_code": "MODULE_NOT_FOUND"
                }
            
            # Read current file
            with open(module_path, 'r') as f:
                current_content = f.read()
            
            # Create backup
            backup_path = module_path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            with open(backup_path, 'w') as f:
                f.write(current_content)
            
            # Append new capability
            updated_content = current_content + "\n\n" + capability_code
            
            # Validate syntax
            try:
                compile(updated_content, module_path, 'exec')
            except SyntaxError as e:
                return {
                    "status": "error",
                    "message": f"Syntax error in capability code: {str(e)}",
                    "error_code": "SYNTAX_ERROR"
                }
            
            # Write updated file
            with open(module_path, 'w') as f:
                f.write(updated_content)
            
            modification = {
                "timestamp": datetime.now().isoformat(),
                "type": "capability",
                "module": module_name,
                "backup_file": backup_path,
                "status": "success"
            }
            self.modification_history.append(modification)
            self._log_modification(modification)
            
            return {
                "status": "success",
                "message": f"Successfully added capability to {module_name}",
                "backup_file": backup_path
            }
            
        except Exception as e:
            logger.error(f"Capability addition error: {str(e)}")
            return {
                "status": "error",
                "message": f"Capability addition failed: {str(e)}",
                "error_code": "CAPABILITY_ADD_FAILED"
            }

    def rollback_modification(self, modification_id: int) -> Dict[str, Any]:
        """
        Rollback a previous modification
        
        Args:
            modification_id: ID of modification to rollback
            
        Returns:
            Status of rollback
        """
        try:
            if modification_id >= len(self.modification_history):
                return {
                    "status": "error",
                    "message": f"Modification ID {modification_id} not found",
                    "error_code": "ID_NOT_FOUND"
                }
            
            modification = self.modification_history[modification_id]
            
            if "backup_file" not in modification:
                return {
                    "status": "error",
                    "message": "No backup file found for this modification",
                    "error_code": "NO_BACKUP"
                }
            
            backup_file = modification["backup_file"]
            if not os.path.exists(backup_file):
                return {
                    "status": "error",
                    "message": f"Backup file {backup_file} not found",
                    "error_code": "BACKUP_NOT_FOUND"
                }
            
            # Get target file path
            if "module" in modification:
                target_file = os.path.join(
                    self.system_root,
                    modification["module"].replace(".", os.sep) + ".py"
                )
            else:
                target_file = backup_file.rsplit(".backup_", 1)[0]
            
            # Restore from backup
            with open(backup_file, 'r') as f:
                backup_content = f.read()
            with open(target_file, 'w') as f:
                f.write(backup_content)
            
            logger.info(f"Successfully rolled back modification {modification_id}")
            rollback_event = {
                "timestamp": datetime.now().isoformat(),
                "type": "rollback",
                "rolled_back_modification_id": modification_id,
                "target_file": target_file,
                "status": "success",
            }
            self.modification_history.append(rollback_event)
            self._log_modification(rollback_event)
            
            return {
                "status": "success",
                "message": f"Successfully rolled back modification {modification_id}",
                "target_file": target_file
            }
            
        except Exception as e:
            logger.error(f"Rollback error: {str(e)}")
            return {
                "status": "error",
                "message": f"Rollback failed: {str(e)}",
                "error_code": "ROLLBACK_FAILED"
            }

    def get_modification_history(self) -> List[Dict[str, Any]]:
        """Get history of all modifications"""
        return self.modification_history

    def _inject_function(self, file_content: str, function_name: str, new_logic: str) -> str:
        """Inject new function logic into file content"""
        lines = file_content.split('\n')
        function_start = -1
        function_end = -1
        indent_level = 0
        
        # Find function definition
        for i, line in enumerate(lines):
            if f'def {function_name}' in line:
                function_start = i
                indent_level = len(line) - len(line.lstrip())
                break
        
        if function_start == -1:
            return file_content
        
        # Find function end (next function or class at same indent level)
        for i in range(function_start + 1, len(lines)):
            stripped = lines[i].lstrip()
            if stripped and not stripped.startswith('#'):
                current_indent = len(lines[i]) - len(stripped)
                if current_indent <= indent_level and (stripped.startswith('def ') or stripped.startswith('class ')):
                    function_end = i
                    break
        
        if function_end == -1:
            function_end = len(lines)
        
        # Replace function
        new_lines = lines[:function_start] + new_logic.split('\n') + lines[function_end:]
        return '\n'.join(new_lines)

    def _validate_code_snippet(self, code: str, expected_function: str = None) -> Dict[str, Any]:
        """Validate snippet syntax and block dangerous operations."""
        if not isinstance(code, str) or not code.strip():
            return {"ok": False, "message": "Code cannot be empty"}

        for token in self.blocked_tokens:
            if token in code:
                return {"ok": False, "message": f"Blocked token detected: {token}"}

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"ok": False, "message": f"Syntax error in code: {e}"}

        if expected_function:
            fn_defs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            if expected_function not in fn_defs:
                return {"ok": False, "message": f"Provided code must define function '{expected_function}'"}

        return {"ok": True, "message": "ok"}

    def _log_modification(self, modification: Dict[str, Any]) -> None:
        """Log modification to file"""
        try:
            with open(self.modifications_log_file, 'a') as f:
                f.write(json.dumps(modification) + '\n')
        except Exception as e:
            logger.error(f"Failed to log modification: {str(e)}")


# Initialize global instance
self_modification_system = SelfModificationSystem()
