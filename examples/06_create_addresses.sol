// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice This predicts an Ethereum CREATE2 address before deployment. A
/// chain-specific CREATE2/deployer rule can invalidate the prediction.
contract EthereumCreate2Prediction {
    function predict(bytes32 salt, bytes32 initCodeHash) external view returns (address) {
        bytes32 digest = keccak256(abi.encodePacked(bytes1(0xff), address(this), salt, initCodeHash));
        return address(uint160(uint256(digest)));
    }
}

/// @notice Store the address returned by the target VM and use that address as
/// the source of truth for registries, approvals, and later calls.
contract RecordActualCreate2Address {
    mapping(bytes32 => address) public deployed;

    event Deployed(bytes32 indexed salt, address indexed instance);

    function deploy(bytes calldata initCode, bytes32 salt) external returns (address instance) {
        bytes memory code = initCode;
        assembly {
            instance := create2(0, add(code, 0x20), mload(code), salt)
        }
        require(instance != address(0), "create2 failed");
        deployed[salt] = instance;
        emit Deployed(salt, instance);
    }
}
