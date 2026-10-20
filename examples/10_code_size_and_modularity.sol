// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice A monolithic build can pass local compilation while exceeding the
/// target chain's init/runtime code limit at deployment.
contract MonolithicDeploymentAssumption {
    bytes32 public immutable buildMarker;

    constructor(bytes32 marker) {
        buildMarker = marker;
    }
}

/// @notice Split large applications into independently measured modules. The
/// target-chain probe still needs to test the actual init and runtime sizes.
contract ModularDelegateDispatcher {
    address public immutable implementation;

    constructor(address implementation_) {
        implementation = implementation_;
    }

    fallback() external payable {
        address target = implementation;
        assembly {
            calldatacopy(0, 0, calldatasize())
            let ok := delegatecall(gas(), target, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch ok
            case 0 { revert(0, returndatasize()) }
            default { return(0, returndatasize()) }
        }
    }

    receive() external payable {}
}
